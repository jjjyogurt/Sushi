from datetime import datetime, timezone

from app.config import get_settings
from app.models.analysis_result import AnalysisResult
from app.models.app_user import AppUser
from app.models.enums import AnalysisStatus, RiskLevel, Sentiment
from app.models.monitor_profile import MonitorProfile
from app.models.video_comment import VideoComment
from app.repositories.video_repository import VideoRepository
from app.services.agent_settings_service import AgentSettingsService
from app.services.analysis_service import AnalysisService
from app.services.exceptions import GeminiResponseError
from app.services.types import AnalysisOutput, CommentsAnalysisOutput, TranscriptOutput
from app.utils.json_codec import decode_json, encode_json


class StubTranscriptService:
    def __init__(self, *, source_language: str = "en", full_text: str = ""):
        self.source_language = source_language
        self.full_text = full_text or (
            "00:12 Setup was easy and fast.\n"
            "02:48 I got confused with advanced controls.\n"
            "05:10 Reliability could be better after one week."
        )

    def fetch_transcript(self, *, youtube_video_id: str, preferred_languages):
        _ = (youtube_video_id, preferred_languages)
        lines = self.full_text.splitlines()
        return TranscriptOutput(
            full_text=self.full_text,
            segments=[
                {"timestamp": line.split(maxsplit=1)[0], "text": line.split(maxsplit=1)[1], "duration": 3.2}
                for line in lines
                if len(line.split(maxsplit=1)) == 2
            ],
            source_language=self.source_language,
        )


class StubGeminiClient:
    def ensure_ready(self):
        return None

    def translate_transcript_bundle(self, *, transcript_text: str, source_language: str):
        _ = source_language
        self.transcript_bundle_call_count = getattr(self, "transcript_bundle_call_count", 0) + 1
        translations = {}
        for language in ("en", "zh-Hans"):
            translated_lines = []
            for line in transcript_text.splitlines():
                parts = line.split(maxsplit=1)
                if len(parts) == 2:
                    translated_lines.append(f"{parts[0]} {language} translation of {parts[1]}")
                else:
                    translated_lines.append(f"{language} translation of {line}")
            translations[language] = "\n".join(translated_lines)
        return translations

    def translate_transcript(self, *, transcript_text: str, source_language: str, target_output_language: str):
        return self.translate_transcript_bundle(
            transcript_text=transcript_text,
            source_language=source_language,
        )[target_output_language]

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
            audience_profiles=[
                {
                    "type": "Primary",
                    "description": "Prospective buyers evaluating setup and reliability tradeoffs.",
                },
                {
                    "type": "Secondary",
                    "description": "Current owners looking for control tips and reliability signals.",
                },
            ],
            usage_scenarios=["onboarding walkthrough", "one-week reliability check"],
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


class CapturingGeminiClient(StubGeminiClient):
    def __init__(self):
        self.agent_instructions_seen = None
        self.source_language_seen = None
        self.transcript_text_seen = None
        self.knowledge_context_seen = None

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
        self.agent_instructions_seen = agent_instructions
        self.source_language_seen = source_language
        self.transcript_text_seen = transcript_text
        self.knowledge_context_seen = knowledge_context
        return super().analyze_video(
            title=title,
            source_language=source_language,
            target_output_language=target_output_language,
            relevance_reason=relevance_reason,
            transcript_text=transcript_text,
            knowledge_context=knowledge_context,
            agent_instructions=agent_instructions,
        )


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


class FailingTranscriptTranslationGeminiClient(StubGeminiClient):
    def __init__(self, *, failed_target_language: str):
        self.failed_target_language = failed_target_language

    def translate_transcript_bundle(self, *, transcript_text: str, source_language: str):
        _ = (transcript_text, source_language)
        self.transcript_bundle_call_count = getattr(self, "transcript_bundle_call_count", 0) + 1
        raise GeminiResponseError(f"{self.failed_target_language} transcript translation failed")

    def translate_transcript(self, *, transcript_text: str, source_language: str, target_output_language: str):
        _ = (transcript_text, source_language)
        if target_output_language == self.failed_target_language:
            raise GeminiResponseError(f"{target_output_language} transcript translation failed")
        return super().translate_transcript(
            transcript_text=transcript_text,
            source_language=source_language,
            target_output_language=target_output_language,
        )


class FailingAnalysisTranslationGeminiClient(StubGeminiClient):
    def translate_analysis_bundle(self, *, analysis_output, comments_output, target_output_language: str):
        _ = (analysis_output, comments_output, target_output_language)
        raise GeminiResponseError("analysis bundle translation failed")


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
    assert parsed_insights_payload["audience_profiles"][0]["type"] == "Primary"
    assert parsed_insights_payload["usage_scenarios"] == ["onboarding walkthrough", "one-week reliability check"]
    assert parsed_insights_payload["action_recommendation"].startswith("Explain improved control tips")

    settings.analysis_version = original_version
    settings.gemini_api_key = original_key


def test_english_source_stores_native_english_and_translated_chinese_transcripts(db_session, discovered_video):
    settings = get_settings()
    original_version = settings.analysis_version
    original_key = settings.gemini_api_key
    settings.analysis_version = "unit-transcript-en-source"
    settings.gemini_api_key = "unit-test-key"
    try:
        service = AnalysisService(db_session)
        service.transcript_service = StubTranscriptService(source_language="en")
        service.gemini_client = StubGeminiClient()

        english = service.analyze_video(video_id=discovered_video.id, force_reanalyze=True)
        chinese = service.analysis_repository.get_latest_for_video(
            video_candidate_id=discovered_video.id,
            language="zh-Hans",
        )

        assert english.transcript_text.startswith("00:12 Setup was easy")
        assert english.transcript_language == "en"
        assert english.transcript_source_language == "en"
        assert english.transcript_is_translated is False
        assert english.transcript_translation_model == ""
        assert english.transcript_status == "available"
        assert english.transcript_error_message == ""
        assert chinese.transcript_text.startswith("00:12 zh-Hans translation of Setup was easy")
        assert chinese.transcript_language == "zh-Hans"
        assert chinese.transcript_source_language == "en"
        assert chinese.transcript_is_translated is True
        assert chinese.transcript_translation_model == settings.gemini_model_analysis
        assert chinese.transcript_status == "available"
        assert chinese.transcript_error_message == ""
        assert service.gemini_client.transcript_bundle_call_count == 1
    finally:
        settings.analysis_version = original_version
        settings.gemini_api_key = original_key


def test_non_english_source_translates_transcripts_for_both_language_rows(db_session, discovered_video):
    settings = get_settings()
    original_version = settings.analysis_version
    original_key = settings.gemini_api_key
    settings.analysis_version = "unit-transcript-ja-source"
    settings.gemini_api_key = "unit-test-key"
    try:
        service = AnalysisService(db_session)
        service.transcript_service = StubTranscriptService(
            source_language="ja",
            full_text="00:01 セットアップは簡単です。\n00:02 操作は少し難しいです。",
        )
        capturing_client = CapturingGeminiClient()
        service.gemini_client = capturing_client

        english = service.analyze_video(video_id=discovered_video.id, force_reanalyze=True)
        chinese = service.analysis_repository.get_latest_for_video(
            video_candidate_id=discovered_video.id,
            language="zh-Hans",
        )

        assert capturing_client.source_language_seen == "ja"
        assert capturing_client.transcript_text_seen == "00:01 セットアップは簡単です。\n00:02 操作は少し難しいです。"
        assert capturing_client.knowledge_context_seen is not None
        assert capturing_client.transcript_bundle_call_count == 1
        assert english.transcript_text.startswith("00:01 en translation of")
        assert english.transcript_language == "en"
        assert english.transcript_source_language == "ja"
        assert english.transcript_is_translated is True
        assert english.transcript_status == "available"
        assert chinese.transcript_text.startswith("00:01 zh-Hans translation of")
        assert chinese.transcript_language == "zh-Hans"
        assert chinese.transcript_source_language == "ja"
        assert chinese.transcript_is_translated is True
        assert chinese.transcript_status == "available"
    finally:
        settings.analysis_version = original_version
        settings.gemini_api_key = original_key


def test_chinese_source_stores_native_chinese_and_translated_english_transcripts(db_session, discovered_video):
    settings = get_settings()
    original_version = settings.analysis_version
    original_key = settings.gemini_api_key
    settings.analysis_version = "unit-transcript-zh-source"
    settings.gemini_api_key = "unit-test-key"
    try:
        service = AnalysisService(db_session)
        service.transcript_service = StubTranscriptService(
            source_language="zh-CN",
            full_text="00:01 设置很简单。\n00:02 控制有一点难。",
        )
        service.gemini_client = StubGeminiClient()

        english = service.analyze_video(video_id=discovered_video.id, force_reanalyze=True)
        chinese = service.analysis_repository.get_latest_for_video(
            video_candidate_id=discovered_video.id,
            language="zh-Hans",
        )

        assert english.transcript_text.startswith("00:01 en translation of")
        assert english.transcript_language == "en"
        assert english.transcript_source_language == "zh-Hans"
        assert english.transcript_is_translated is True
        assert english.transcript_status == "available"
        assert service.gemini_client.transcript_bundle_call_count == 1
        assert chinese.transcript_text == "00:01 设置很简单。\n00:02 控制有一点难。"
        assert chinese.transcript_language == "zh-Hans"
        assert chinese.transcript_source_language == "zh-Hans"
        assert chinese.transcript_is_translated is False
        assert chinese.transcript_status == "available"
    finally:
        settings.analysis_version = original_version
        settings.gemini_api_key = original_key


def test_chinese_transcript_translation_failure_preserves_chinese_analysis_with_transcript_warning(db_session, discovered_video):
    settings = get_settings()
    original_version = settings.analysis_version
    original_key = settings.gemini_api_key
    settings.analysis_version = "unit-transcript-zh-fail"
    settings.gemini_api_key = "unit-test-key"
    try:
        service = AnalysisService(db_session)
        service.transcript_service = StubTranscriptService(source_language="en")
        service.gemini_client = FailingTranscriptTranslationGeminiClient(failed_target_language="zh-Hans")

        english = service.analyze_video(video_id=discovered_video.id, force_reanalyze=True)
        chinese = service.analysis_repository.get_latest_for_video(
            video_candidate_id=discovered_video.id,
            language="zh-Hans",
        )

        assert english.status == AnalysisStatus.COMPLETED
        assert english.transcript_text.startswith("00:12 Setup was easy")
        assert chinese.status == AnalysisStatus.COMPLETED
        assert chinese.summary_text
        assert chinese.transcript_text == ""
        assert chinese.transcript_language == "zh-Hans"
        assert chinese.transcript_source_language == "en"
        assert chinese.transcript_is_translated is True
        assert chinese.transcript_translation_model == settings.gemini_model_analysis
        assert chinese.transcript_status == "unavailable"
        assert "TRANSCRIPT_TRANSLATION_FAILED" in chinese.transcript_error_message
        assert chinese.error_message == ""
    finally:
        settings.analysis_version = original_version
        settings.gemini_api_key = original_key


def test_english_transcript_translation_failure_preserves_analysis_with_transcript_warning(db_session, discovered_video):
    settings = get_settings()
    original_version = settings.analysis_version
    original_key = settings.gemini_api_key
    settings.analysis_version = "unit-transcript-en-fail"
    settings.gemini_api_key = "unit-test-key"
    try:
        service = AnalysisService(db_session)
        service.transcript_service = StubTranscriptService(source_language="ja")
        service.gemini_client = FailingTranscriptTranslationGeminiClient(failed_target_language="en")

        english = service.analyze_video(video_id=discovered_video.id, force_reanalyze=True)
        english = service.analysis_repository.get_latest_for_video(
            video_candidate_id=discovered_video.id,
            language="en",
        )
        chinese = service.analysis_repository.get_latest_for_video(
            video_candidate_id=discovered_video.id,
            language="zh-Hans",
        )
        assert english.status == AnalysisStatus.COMPLETED
        assert english.summary_text
        assert english.transcript_text == ""
        assert english.transcript_language == "en"
        assert english.transcript_source_language == "ja"
        assert english.transcript_is_translated is True
        assert english.transcript_status == "unavailable"
        assert "TRANSCRIPT_TRANSLATION_FAILED" in english.transcript_error_message
        assert english.error_message == ""
        assert chinese.status == AnalysisStatus.COMPLETED
        assert chinese.summary_text
        assert chinese.transcript_text == ""
        assert chinese.transcript_language == "zh-Hans"
        assert chinese.transcript_source_language == "ja"
        assert chinese.transcript_is_translated is True
        assert chinese.transcript_status == "unavailable"
        assert "TRANSCRIPT_TRANSLATION_FAILED" in chinese.transcript_error_message
    finally:
        settings.analysis_version = original_version
        settings.gemini_api_key = original_key


def test_chinese_analysis_translation_failure_fails_only_chinese_row(db_session, discovered_video):
    settings = get_settings()
    original_version = settings.analysis_version
    original_key = settings.gemini_api_key
    settings.analysis_version = "unit-analysis-zh-fail"
    settings.gemini_api_key = "unit-test-key"
    try:
        service = AnalysisService(db_session)
        service.transcript_service = StubTranscriptService(source_language="en")
        service.gemini_client = FailingAnalysisTranslationGeminiClient()

        english = service.analyze_video(video_id=discovered_video.id, force_reanalyze=True)
        chinese = service.analysis_repository.get_latest_for_video(
            video_candidate_id=discovered_video.id,
            language="zh-Hans",
        )

        assert english.status == AnalysisStatus.COMPLETED
        assert english.summary_text
        assert chinese.status == AnalysisStatus.FAILED
        assert chinese.summary_text == ""
        assert chinese.transcript_text == ""
        assert "analysis bundle translation failed" in chinese.error_message
    finally:
        settings.analysis_version = original_version
        settings.gemini_api_key = original_key


def test_new_analysis_uses_latest_saved_account_agent_prompt(db_session, discovered_video):
    settings = get_settings()
    original_version = settings.analysis_version
    original_key = settings.gemini_api_key
    latest_prompt = "Use the updated account-specific prompt for new video analysis."
    settings.analysis_version = "unit-latest-agent-prompt"
    settings.gemini_api_key = "unit-test-key"
    try:
        AgentSettingsService(db_session).save_content(
            user_id=discovered_video.monitor_profile.owner_user_id,
            content=latest_prompt,
        )
        capturing_client = CapturingGeminiClient()
        service = AnalysisService(db_session)
        service.transcript_service = StubTranscriptService()
        service.gemini_client = capturing_client

        result = service.analyze_video(video_id=discovered_video.id, force_reanalyze=False)

        assert result.status == AnalysisStatus.COMPLETED
        assert capturing_client.agent_instructions_seen == latest_prompt
        assert result.agent_settings_hash == AgentSettingsService.hash_content(latest_prompt)
    finally:
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
    assert failed.transcript_language == ""
    assert failed.transcript_source_language == ""
    assert failed.transcript_is_translated is False
    assert failed.transcript_translation_model == ""
    assert failed.transcript_status == ""
    assert failed.transcript_error_message == ""
    assert failed.translated_summary == ""
    assert failed.summary_headline == ""
    assert failed.summary_body == ""
    assert failed.evidence_json == "[]"
    assert failed.insights_json == "{}"
    assert failed.error_message

    settings.analysis_version = original_version
    settings.gemini_api_key = original_key


def test_comment_refresh_rolls_back_failed_sync_before_reading_existing_comments(db_session, discovered_video):
    service = AnalysisService(db_session)
    now = datetime.now(timezone.utc)

    def poison_comment_sync(*, video_candidate_id: int, comments):
        _ = comments
        db_session.add(
            VideoComment(
                video_candidate_id=video_candidate_id,
                youtube_comment_id="poison-comment",
                parent_comment_id="",
                author_name="Viewer",
                text="Existing usable comment",
                like_count=0,
                published_at=now,
                updated_at_remote=now,
                is_reply=False,
            )
        )
        db_session.commit()
        db_session.add(
            VideoComment(
                video_candidate_id=video_candidate_id,
                youtube_comment_id="poison-comment",
                parent_comment_id="",
                author_name="Viewer",
                text="Duplicate comment",
                like_count=0,
                published_at=now,
                updated_at_remote=now,
                is_reply=False,
            )
        )
        db_session.commit()

    service.youtube_comments_service.fetch_all_comments = lambda youtube_video_id: [{"youtube_comment_id": "poison-comment"}]
    service.video_comment_repository.replace_for_video = poison_comment_sync

    comments = service._refresh_video_comments(
        video_id=discovered_video.id,
        youtube_video_id=discovered_video.youtube_video_id,
        request_id="unit-rollback",
    )

    assert comments == ["Existing usable comment"]
