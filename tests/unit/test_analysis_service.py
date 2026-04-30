from app.config import get_settings
from app.models.analysis_result import AnalysisResult
from app.models.enums import AnalysisStatus, RiskLevel, Sentiment
from app.services.analysis_service import AnalysisService
from app.services.types import AnalysisOutput, CommentsAnalysisOutput, TranscriptOutput
from app.utils.json_codec import decode_json, encode_json


class StubTranscriptService:
    def fetch_transcript(self, *, youtube_video_id: str, preferred_languages):
        return TranscriptOutput(
            full_text=(
                "00:12 Setup was easy and fast.\n"
                "02:48 I got confused with advanced controls.\n"
                "05:10 Reliability could be better after one week."
            ),
            segments=[
                {"timestamp": "00:12", "text": "Setup was easy and fast.", "duration": 3.2},
                {"timestamp": "02:48", "text": "I got confused with advanced controls.", "duration": 4.0},
                {"timestamp": "05:10", "text": "Reliability could be better after one week.", "duration": 4.5},
            ],
            source_language=preferred_languages[0] if preferred_languages else "en",
        )


class StubGeminiClient:
    def ensure_ready(self):
        return None

    def analyze_video(
        self,
        *,
        title: str,
        source_language: str,
        target_output_language: str,
        relevance_reason: str,
        transcript_text: str,
        knowledge_context: str = "",
    ):
        _ = (knowledge_context, source_language, target_output_language)
        return AnalysisOutput(
            transcript_text=transcript_text,
            summary_text=f"{title} includes onboarding and reliability concerns.",
            translated_summary=f"{title} includes onboarding and reliability concerns.",
            summary_headline="Reliability concerns surfaced during influencer walkthrough.",
            summary_body="Sentiment is neutral with meaningful reliability and control friction noted in transcript evidence.",
            sentiment=Sentiment.NEUTRAL,
            risk_level=RiskLevel.MEDIUM,
            confidence_score=0.84,
            evidence=[
                {"timestamp": "02:48", "quote": "I got confused with advanced controls.", "reason": "Usability risk"},
                {"timestamp": "05:10", "quote": "Reliability could be better after one week.", "reason": "Reliability risk"},
            ],
            insights=["Onboarding confusion is recurring.", "Reliability concerns can affect trust."],
            praise_points=["Setup was easy and fast."],
            criticism_points=["Advanced controls felt confusing.", "Reliability concerns appeared after one week."],
            action_recommendation="Explain improved control tips and reliability roadmap to the influencer.",
        )

    def analyze_comments(self, *, title: str, language: str, comments):
        _ = (title, language, comments)
        return CommentsAnalysisOutput(
            summary="Comments are mixed with strong interest but clear concerns about reliability.",
            highlights=[
                {"point": "Compact design is appreciated.", "quote": "love how small this is"},
                {"point": "Flight is quiet.", "quote": "so quiet in flight"},
            ],
            lowlights=[
                {"point": "Reliability concerns remain.", "quote": "not sure it will last"},
            ],
        )

    def translate_analysis_bundle(self, *, analysis_output, comments_output, target_output_language: str):
        _ = target_output_language
        return analysis_output, comments_output


class StubFailingGeminiClient:
    def ensure_ready(self):
        return None

    def analyze_video(
        self,
        *,
        title: str,
        source_language: str,
        target_output_language: str,
        relevance_reason: str,
        transcript_text: str,
        knowledge_context: str = "",
    ):
        _ = (title, source_language, target_output_language, relevance_reason, transcript_text, knowledge_context)
        raise RuntimeError("provider exploded")


def test_skip_reanalysis_when_completed_and_same_version(db_session, discovered_video):
    settings = get_settings()
    original_version = settings.analysis_version
    settings.analysis_version = "unit-v1"

    existing_en = AnalysisResult(
        video_candidate_id=discovered_video.id,
        analysis_version="unit-v1",
        language="en",
        model_name="gemini-3",
        status=AnalysisStatus.COMPLETED,
        transcript_text="cached transcript",
        summary_text="cached summary",
        translated_summary="cached summary",
        sentiment=Sentiment.NEUTRAL,
        risk_level=RiskLevel.MEDIUM,
        confidence_score="0.88",
        evidence_json=encode_json([{"timestamp": "00:10", "quote": "cached", "reason": "cache"}]),
        insights_json=encode_json(["cached"]),
    )
    existing_zh = AnalysisResult(
        video_candidate_id=discovered_video.id,
        analysis_version="unit-v1",
        language="zh-Hans",
        model_name="gemini-3",
        status=AnalysisStatus.COMPLETED,
        transcript_text="cached transcript zh",
        summary_text="cached summary zh",
        translated_summary="cached summary zh",
        sentiment=Sentiment.NEUTRAL,
        risk_level=RiskLevel.MEDIUM,
        confidence_score="0.88",
        evidence_json=encode_json([{"timestamp": "00:10", "quote": "cached zh", "reason": "cache"}]),
        insights_json=encode_json(["cached zh"]),
    )
    db_session.add(existing_en)
    db_session.add(existing_zh)
    db_session.commit()
    db_session.refresh(existing_en)

    service = AnalysisService(db_session)
    result = service.analyze_video(video_id=discovered_video.id, force_reanalyze=False)

    assert result.id == existing_en.id
    assert result.summary_text == "cached summary"

    settings.analysis_version = original_version


def test_force_reanalysis_reuses_version_record_and_refreshes_result(db_session, discovered_video):
    settings = get_settings()
    original_version = settings.analysis_version
    original_key = settings.gemini_api_key
    settings.analysis_version = "unit-v2"
    settings.gemini_api_key = "unit-test-key"

    service = AnalysisService(db_session)
    service.transcript_service = StubTranscriptService()
    service.gemini_client = StubGeminiClient()
    first = service.analyze_video(video_id=discovered_video.id, force_reanalyze=False)
    second = service.analyze_video(video_id=discovered_video.id, force_reanalyze=True)

    assert first.id == second.id
    assert second.status == AnalysisStatus.COMPLETED
    assert "05:10 Reliability could be better after one week." in second.transcript_text
    assert second.evidence_json != "[]"
    assert second.summary_headline.startswith("Reliability concerns")
    assert second.summary_body.startswith("Sentiment is neutral")
    assert second.comment_summary_text.startswith("Comments are mixed")
    assert decode_json(second.comment_highlights_json, [])[0]["point"] == "Compact design is appreciated."
    assert decode_json(second.comment_lowlights_json, [])[0]["quote"] == "not sure it will last"
    parsed_insights_payload = decode_json(second.insights_json, {})
    assert parsed_insights_payload["praise_points"] == ["Setup was easy and fast."]
    assert parsed_insights_payload["action_recommendation"].startswith("Explain improved control tips")

    settings.analysis_version = original_version
    settings.gemini_api_key = original_key


def test_analysis_fails_closed_when_gemini_is_unavailable(db_session, discovered_video):
    settings = get_settings()
    original_version = settings.analysis_version
    original_key = settings.gemini_api_key
    settings.analysis_version = "unit-fail-closed"
    settings.gemini_api_key = ""

    service = AnalysisService(db_session)
    service.transcript_service = StubTranscriptService()

    try:
        service.analyze_video(video_id=discovered_video.id, force_reanalyze=True)
    except RuntimeError as error:
        assert "GEMINI_API_KEY" in str(error)
    else:
        raise AssertionError("Expected fail-closed Gemini runtime error.")

    failed = service.analysis_repository.get_latest_for_video(video_candidate_id=discovered_video.id)
    assert failed is None

    settings.analysis_version = original_version
    settings.gemini_api_key = original_key


def test_analysis_runs_without_approval_state(db_session, discovered_video):
    settings = get_settings()
    original_version = settings.analysis_version
    original_key = settings.gemini_api_key
    settings.analysis_version = "unit-without-approval"
    settings.gemini_api_key = "unit-test-key"

    service = AnalysisService(db_session)
    service.transcript_service = StubTranscriptService()
    service.gemini_client = StubGeminiClient()
    result = service.analyze_video(video_id=discovered_video.id, force_reanalyze=True)

    assert result.status == AnalysisStatus.COMPLETED
    assert result.summary_text
    assert result.transcript_text

    settings.analysis_version = original_version
    settings.gemini_api_key = original_key


def test_force_rerun_failure_clears_previous_payload(db_session, discovered_video):
    settings = get_settings()
    original_version = settings.analysis_version
    original_key = settings.gemini_api_key
    settings.analysis_version = "unit-rerun-fail-clean"
    settings.gemini_api_key = "unit-test-key"

    service = AnalysisService(db_session)
    service.transcript_service = StubTranscriptService()
    service.gemini_client = StubGeminiClient()
    baseline = service.analyze_video(video_id=discovered_video.id, force_reanalyze=False)

    service.gemini_client = StubFailingGeminiClient()
    try:
        service.analyze_video(video_id=discovered_video.id, force_reanalyze=True)
    except RuntimeError as error:
        assert "provider exploded" in str(error)
    else:
        raise AssertionError("Expected rerun to fail with provider exploded.")

    failed = service.analysis_repository.get_latest_for_video(video_candidate_id=discovered_video.id)
    assert failed is not None
    assert failed.id == baseline.id
    assert failed.status == AnalysisStatus.FAILED
    assert failed.summary_text == ""
    assert failed.transcript_text == ""
    assert failed.translated_summary == ""
    assert failed.summary_headline == ""
    assert failed.summary_body == ""
    assert failed.evidence_json == "[]"
    assert failed.insights_json == "{}"
    assert failed.error_message

    settings.analysis_version = original_version
    settings.gemini_api_key = original_key

