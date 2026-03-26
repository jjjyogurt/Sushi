import pytest

from app.config import Settings
from app.services.exceptions import GeminiResponseError
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
        return head


def _build_settings() -> Settings:
    return Settings(
        gemini_api_key="unit-test-key",
        analysis_chunk_chars=90,
        analysis_chunk_overlap_chars=12,
        analysis_max_chunks=6,
        analysis_max_transcript_chars=3000,
    )


def _chunk_response(summary: str) -> str:
    return (
        '{'
        f'"summary_text":"{summary}",'
        '"translated_summary":"translated",'
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
    responses = [_chunk_response(summary=f"chunk-{index}") for index in range(chunk_count)] + [
        (
            '{"summary_text":"final summary",'
            '"translated_summary":"final summary",'
            '"sentiment":"negative",'
            '"risk_level":"high",'
            '"confidence_score":0.91,'
            '"evidence":[{"timestamp":"01:20","quote":"Reliability concerns appear after one week.","reason":"core risk"}],'
            '"insights":["Priority: address reliability messaging."],'
            '"praise_points":["easy setup","good stabilization","strong camera quality","portable form factor","good value"],'
            '"criticism_points":["control complexity","signal loss","obstacle sensing gap","manual UX friction","price concern","extra item should be ignored"],'
            '"action_recommendation":"Explain reliability improvements and offer setup checklist to the influencer."}'
        )
    ]
    client = DeterministicGeminiClient(settings, responses=responses)

    output = client.analyze_video(
        title="Unit Test Video",
        language="en",
        relevance_reason="keyword match",
        transcript_text=transcript,
    )

    assert output.summary_text == "final summary"
    assert output.risk_level.value == "high"
    assert len(output.praise_points) == 5
    assert len(output.criticism_points) == 5
    assert output.criticism_points[-1] == "price concern"
    assert output.action_recommendation.startswith("Explain reliability improvements")
    assert len(client.prompts) == chunk_count + 1
    assert "Chunk: 1 of" in client.prompts[0]
    assert "Chunk analyses JSON" in client.prompts[-1]


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
            language="en",
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
