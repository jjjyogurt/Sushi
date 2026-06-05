import json

import pytest

from app.config import Settings
from app.services.exceptions import GeminiProviderError, GeminiResponseError
from app.services.gemini_client import GeminiClient


class DeterministicGeminiClient(GeminiClient):
    def __init__(self, settings: Settings, responses):
        super().__init__(settings)
        self.responses = list(responses)
        self.prompts = []

    def _ensure_runtime_ready(self) -> None:
        return None

    def _generate_text(self, *, model_name: str, prompt: str) -> str:
        _ = model_name
        self.prompts = [*self.prompts, prompt]
        if not self.responses:
            raise AssertionError("No response left in deterministic Gemini client.")
        head = self.responses[0]
        self.responses = self.responses[1:]
        if isinstance(head, Exception):
            raise head
        return head


def _build_settings(**overrides) -> Settings:
    alias_by_field_name = {
        "gemini_api_key": "GEMINI_API_KEY",
        "analysis_chunk_chars": "ANALYSIS_CHUNK_CHARS",
        "analysis_chunk_overlap_chars": "ANALYSIS_CHUNK_OVERLAP_CHARS",
        "analysis_max_chunks": "ANALYSIS_MAX_CHUNKS",
        "analysis_max_transcript_chars": "ANALYSIS_MAX_TRANSCRIPT_CHARS",
        "analysis_single_pass_max_estimated_tokens": "ANALYSIS_SINGLE_PASS_MAX_ESTIMATED_TOKENS",
        "analysis_estimated_chars_per_token": "ANALYSIS_ESTIMATED_CHARS_PER_TOKEN",
    }
    base_values = {
        "GEMINI_API_KEY": "unit-test-key",
        "ANALYSIS_CHUNK_CHARS": 90,
        "ANALYSIS_CHUNK_OVERLAP_CHARS": 12,
        "ANALYSIS_MAX_CHUNKS": 6,
        "ANALYSIS_MAX_TRANSCRIPT_CHARS": 3000,
        "ANALYSIS_SINGLE_PASS_MAX_ESTIMATED_TOKENS": 1,
        "ANALYSIS_ESTIMATED_CHARS_PER_TOKEN": 4,
    }
    normalized_overrides = {
        alias_by_field_name.get(key, key): value
        for key, value in overrides.items()
    }
    return Settings(**{**base_values, **normalized_overrides})


def _chunk_response(summary: str) -> str:
    return (
        '{'
        f'"summary_text":"{summary}",'
        '"translated_summary":"translated",'
        '"summary_headline":"chunk headline",'
        '"summary_body":"chunk body",'
        ''
        '"sentiment":"neutral",'
        '"risk_level":"medium",'
        '"confidence_score":0.75,'
        '"evidence":[{"timestamp":"00:10","quote":"evidence","reason":"signal"}],'
        '"insights":["chunk insight"],'
        '"praise_points":["easy setup","stable footage"],'
        '"criticism_points":["manual control is hard"],'
        '"action_recommendation":"Explain setup process in clearer steps."'
        '}'
    )


def _final_response(*, summary_text: str = "final summary") -> str:
    return (
        '{'
        f'"summary_text":"{summary_text}",'
        '"translated_summary":"final summary",'
        '"summary_headline":"final headline",'
        '"summary_body":"final body",'
        ''
        '"sentiment":"negative",'
        '"risk_level":"high",'
        '"confidence_score":0.91,'
        '"evidence":[{"timestamp":"01:20","quote":"Reliability concerns appear after one week.","reason":"core risk"}],'
        '"insights":["Priority: address reliability messaging."],'
        '"praise_points":["easy setup","good stabilization","strong camera quality","portable form factor","good value"],'
        '"criticism_points":["control complexity","signal loss","obstacle sensing gap","manual UX friction","price concern","extra item should be ignored"],'
        '"action_recommendation":"Explain reliability improvements and offer setup checklist to the influencer."}'
    )


def test_analyze_video_uses_chunk_map_reduce_pipeline():
    transcript = "\n".join(
        [
            "00:01 The setup is easy for most users.",
            "00:20 The controls are confusing during first use.",
            "00:40 Support helped after a delayed response.",
            "01:00 Battery drain is acceptable for short clips.",
            "01:20 Reliability concerns appear after one week.",
            "01:40 The creator still recommends the product with caveats.",
        ]
    )
    settings = _build_settings()
    probe_client = DeterministicGeminiClient(settings, responses=[])
    chunk_count = len(probe_client._chunk_transcript(transcript_text=transcript))
    responses = [_chunk_response(summary=f"chunk-{index}") for index in range(chunk_count)] + [_final_response()]
    client = DeterministicGeminiClient(settings, responses=responses)

    output = client.analyze_video(
        title="Unit Test Video",
        source_language="en",
        target_output_language="en",
        relevance_reason="keyword match",
        transcript_text=transcript,
    )

    assert output.summary_text == "final summary"
    assert output.summary_headline == "final headline"
    assert output.summary_body == "final body"
    assert output.risk_level.value == "high"
    assert len(output.praise_points) == 5
    assert len(output.criticism_points) == 5
    assert output.criticism_points[-1] == "price concern"
    assert output.action_recommendation.startswith("Explain reliability improvements")
    assert len(client.prompts) == chunk_count + 1
    assert "Chunk: 1 of" in client.prompts[0]
    assert "Chunk analyses JSON" in client.prompts[-1]


def test_analyze_video_uses_single_pass_when_under_threshold():
    transcript = "00:01 setup is easy\n00:02 footage is stable\n00:03 creator recommends it"
    settings = _build_settings(
        analysis_single_pass_max_estimated_tokens=5000,
        analysis_estimated_chars_per_token=4,
    )
    client = DeterministicGeminiClient(settings, responses=[_final_response(summary_text="single-pass summary")])

    output = client.analyze_video(
        title="Single Pass Video",
        source_language="en",
        target_output_language="en",
        relevance_reason="direct match",
        transcript_text=transcript,
        knowledge_context="Product note: includes stabilization mode.",
    )

    assert output.summary_text == "single-pass summary"
    assert output.transcript_text == transcript
    assert len(client.prompts) == 1
    assert "Transcript:\n00:01 setup is easy" in client.prompts[0]
    assert "Chunk analyses JSON" not in client.prompts[0]


def test_analyze_video_falls_back_to_chunk_reduce_on_single_pass_oversize():
    transcript = "\n".join(
        [
            "00:01 The setup is easy for most users.",
            "00:20 The controls are confusing during first use.",
            "00:40 Support helped after a delayed response.",
            "01:00 Battery drain is acceptable for short clips.",
            "01:20 Reliability concerns appear after one week.",
            "01:40 The creator still recommends the product with caveats.",
        ]
    )
    settings = _build_settings(
        analysis_single_pass_max_estimated_tokens=5000,
        analysis_estimated_chars_per_token=4,
    )
    probe_client = DeterministicGeminiClient(settings, responses=[])
    chunk_count = len(probe_client._chunk_transcript(transcript_text=transcript))
    responses = [
        GeminiProviderError("Gemini request failed: input token count exceeds maximum context length"),
        *[_chunk_response(summary=f"chunk-{index}") for index in range(chunk_count)],
        _final_response(summary_text="fallback summary"),
    ]
    client = DeterministicGeminiClient(settings, responses=responses)

    output = client.analyze_video(
        title="Fallback Video",
        source_language="en",
        target_output_language="en",
        relevance_reason="keyword match",
        transcript_text=transcript,
    )

    assert output.summary_text == "fallback summary"
    assert len(client.prompts) == chunk_count + 2
    assert "Transcript:\n" in client.prompts[0]
    assert "Chunk: 1 of" in client.prompts[1]
    assert "Chunk analyses JSON" in client.prompts[-1]


def test_analyze_video_applies_hard_cap_before_single_pass():
    transcript = "0123456789abcdefghijklmnopqrstuvwxyz"
    settings = _build_settings(
        analysis_max_transcript_chars=20,
        analysis_single_pass_max_estimated_tokens=5000,
        analysis_estimated_chars_per_token=4,
    )
    client = DeterministicGeminiClient(settings, responses=[_final_response(summary_text="capped summary")])

    output = client.analyze_video(
        title="Hard Cap Video",
        source_language="en",
        target_output_language="en",
        relevance_reason="test",
        transcript_text=transcript,
    )

    assert output.summary_text == "capped summary"
    assert output.transcript_text == transcript
    assert "Transcript:\n0123456789abcdefghij\n" in client.prompts[0]
    assert "klmnopqrstuvwxyz" not in client.prompts[0]


def test_analyze_video_raises_on_malformed_reducer_json():
    transcript = "00:01 one\n00:02 two\n00:03 three\n00:04 four"
    settings = _build_settings()
    probe_client = DeterministicGeminiClient(settings, responses=[])
    chunk_count = len(probe_client._chunk_transcript(transcript_text=transcript))
    responses = [_chunk_response(summary=f"chunk-{index}") for index in range(chunk_count)] + [
        "not-json-output",
    ]
    client = DeterministicGeminiClient(settings, responses=responses)

    with pytest.raises(GeminiResponseError):
        client.analyze_video(
            title="Broken Reducer",
            source_language="en",
            target_output_language="en",
            relevance_reason="test",
            transcript_text=transcript,
        )


def test_chat_raises_when_content_missing():
    client = DeterministicGeminiClient(
        _build_settings(),
        responses=['{"citations": [], "confidence_score": 0.3, "insufficient_evidence": true}'],
    )

    with pytest.raises(GeminiResponseError):
        client.chat_about_video(context="summary context", question="Any issues?", language="en")


def test_translate_transcript_bundle_requests_english_and_chinese():
    client = DeterministicGeminiClient(
        _build_settings(),
        responses=[
            (
                "<english_transcript>\n"
                "00:01 translated setup is easy\n"
                "00:02 translated controls are hard\n"
                "</english_transcript>\n"
                "<chinese_transcript>\n"
                "00:01 翻译后的设置很简单\n"
                "00:02 翻译后的控制很难\n"
                "</chinese_transcript>"
            ),
        ],
    )

    output = client.translate_transcript_bundle(
        transcript_text="00:01 setup is easy\n00:02 controls are hard",
        source_language="ja",
    )

    assert output == {
        "en": "00:01 translated setup is easy\n00:02 translated controls are hard",
        "zh-Hans": "00:01 翻译后的设置很简单\n00:02 翻译后的控制很难",
    }
    assert "<english_transcript>" in client.prompts[0]
    assert "<chinese_transcript>" in client.prompts[0]
    assert "Translate this video transcript into English and Simplified Chinese." in client.prompts[0]
    assert "Format each transcript as one timestamped segment per line" in client.prompts[0]
    assert "Do not merge timestamped segments into a single paragraph." in client.prompts[0]
    assert "Do not summarize, omit, or add interpretation." in client.prompts[0]
    assert "line indexes" not in client.prompts[0]


def test_translate_transcript_bundle_handles_japanese_multiline_jsonish_response():
    client = DeterministicGeminiClient(
        _build_settings(),
        responses=[
            (
                '{"english_transcript":"00:00 Hello everyone.\\n'
                '00:01 Today we review the HOVERAir X1 PRO MAX.",'
                '"chinese_transcript":"00:00 大家好。\\n'
                '00:01 今天评测 HOVERAir X1 PRO MAX。"}'
            ).replace("\\n", "\n"),
        ],
    )

    output = client.translate_transcript_bundle(
        transcript_text="00:00 皆さん、こんにちは。\n00:01 HOVERAir X1 PRO MAXをレビューします。",
        source_language="ja",
    )

    assert output["en"] == "00:00 Hello everyone.\n00:01 Today we review the HOVERAir X1 PRO MAX."
    assert output["zh-Hans"] == "00:00 大家好。\n00:01 今天评测 HOVERAir X1 PRO MAX。"


def test_translate_transcript_bundle_splits_collapsed_timestamped_output():
    client = DeterministicGeminiClient(
        _build_settings(),
        responses=[
            json.dumps(
                {
                    "english_transcript": "00:01 translated setup is easy 00:02 translated controls are hard",
                    "chinese_transcript": "00:01 翻译后的设置很简单 00:02 翻译后的控制很难",
                }
            ),
        ],
    )

    output = client.translate_transcript_bundle(
        transcript_text="00:01 setup is easy\n00:02 controls are hard",
        source_language="ja",
    )

    assert output["en"] == "00:01 translated setup is easy\n00:02 translated controls are hard"
    assert output["zh-Hans"] == "00:01 翻译后的设置很简单\n00:02 翻译后的控制很难"


def test_translate_transcript_returns_requested_language_from_bundle():
    client = DeterministicGeminiClient(
        _build_settings(),
        responses=[
            json.dumps(
                {
                    "english_transcript": "00:01 translated setup is easy",
                    "chinese_transcript": "00:01 翻译后的设置很简单",
                }
            ),
        ],
    )

    output = client.translate_transcript(
        transcript_text="00:01 setup is easy",
        source_language="ja",
        target_output_language="zh-Hans",
    )

    assert output == "00:01 翻译后的设置很简单"
    assert len(client.prompts) == 1


def test_translate_transcript_raises_on_empty_output():
    client = DeterministicGeminiClient(_build_settings(), responses=[""])

    with pytest.raises(GeminiResponseError):
        client.translate_transcript(
            transcript_text="00:01 setup is easy",
            source_language="en",
            target_output_language="zh-Hans",
        )


def test_translate_transcript_bundle_raises_when_language_missing():
    client = DeterministicGeminiClient(
        _build_settings(),
        responses=[
            json.dumps({"english_transcript": "00:01 translated setup is easy"}),
        ],
    )

    with pytest.raises(GeminiResponseError):
        client.translate_transcript_bundle(
            transcript_text="00:01 setup is easy\n00:02 controls are hard",
            source_language="ja",
        )
