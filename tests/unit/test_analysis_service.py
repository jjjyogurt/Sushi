from datetime import datetime, timezone

from app.config import get_settings
from app.models.analysis_result import AnalysisResult
from app.models.app_user import AppUser
from app.models.enums import AnalysisStatus, RiskLevel, Sentiment
from app.models.monitor_profile import MonitorProfile
from app.repositories.video_repository import VideoRepository
from app.services.agent_settings_service import AgentSettingsService
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
        agent_instructions: str = "",
    ):
        _ = (knowledge_context, source_language, target_output_language, agent_instructions)
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
        agent_instructions: str = "",
    ):
        _ = (title, source_language, target_output_language, relevance_reason, transcript_text, knowledge_context, agent_instructions)
        raise RuntimeError("provider exploded")


def _seed_user(db_session, user_id: str):
    db_session.add(AppUser(id=user_id, display_name=user_id, password_hash="hash", must_change_password=False, is_active=True))
    db_session.commit()


def _seed_profile(db_session, *, owner_user_id: str, name: str):
    profile = MonitorProfile(
        owner_user_id=owner_user_id,
        name=name,
        brand_keywords=encode_json(["hoverair"]),
        markets=encode_json(["global"]),
        languages=encode_json(["en"]),
        key_products=encode_json([]),
        alert_sensitivity="medium",
        is_active=True,
    )
    db_session.add(profile)
    db_session.commit()
    db_session.refresh(profile)
    return profile


def test_skip_reanalysis_when_completed_and_same_version(db_session, discovered_video):
    settings = get_settings()
    original_version = settings.analysis_version
    settings.analysis_version = "unit-v1"
    settings_hash = AgentSettingsService(db_session).get_resolved(user_id=discovered_video.monitor_profile.owner_user_id).settings_hash

    existing_en = AnalysisResult(
        video_candidate_id=discovered_video.id,
        analysis_version="unit-v1",
        language="en",
        agent_settings_hash=settings_hash,
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
        agent_settings_hash=settings_hash,
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


def test_analysis_cache_is_separated_by_project_owner_agent_settings(db_session):
    settings = get_settings()
    original_version = settings.analysis_version
    original_key = settings.gemini_api_key
    settings.analysis_version = "unit-settings-hash"
    settings.gemini_api_key = "unit-test-key"
    try:
        _seed_user(db_session, "Sushi_A")
        _seed_user(db_session, "Sushi_B")
        profile_a = _seed_profile(db_session, owner_user_id="Sushi_A", name="A Project")
        profile_b = _seed_profile(db_session, owner_user_id="Sushi_B", name="B Project")
        settings_service = AgentSettingsService(db_session)
        settings_service.save_content(user_id="Sushi_A", content="Analyze with safety emphasis.")
        settings_service.save_content(user_id="Sushi_B", content="Analyze with marketing emphasis.")
        repository = VideoRepository(db_session)
        video_a = repository.upsert_candidate(
            monitor_profile_id=profile_a.id,
            youtube_video_id="same-analysis-video",
            video_url="https://youtu.be/same-analysis-video",
            title="Same video A",
            channel_name="Creator",
            language="en",
            published_at=datetime.now(timezone.utc),
            relevance_score=0.8,
            relevance_reason="seed",
        )
        video_b = repository.upsert_candidate(
            monitor_profile_id=profile_b.id,
            youtube_video_id="same-analysis-video",
            video_url="https://youtu.be/same-analysis-video",
            title="Same video B",
            channel_name="Creator",
            language="en",
            published_at=datetime.now(timezone.utc),
            relevance_score=0.8,
            relevance_reason="seed",
        )

        service = AnalysisService(db_session)
        service.transcript_service = StubTranscriptService()
        service.gemini_client = StubGeminiClient()
        result_a = service.analyze_video(video_id=video_a.id, force_reanalyze=False)
        result_b = service.analyze_video(video_id=video_b.id, force_reanalyze=False)

        assert result_a.video_candidate_id == video_a.id
        assert result_b.video_candidate_id == video_b.id
        assert result_a.agent_settings_hash != result_b.agent_settings_hash
        assert result_a.id != result_b.id
    finally:
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
