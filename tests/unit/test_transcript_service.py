import pytest

from app.config import get_settings
from app.services.exceptions import (
    TranscriptBlockedError,
    TranscriptProviderError,
    TranscriptUnavailableError,
)
from app.services.transcript_service import TranscriptService


@pytest.fixture(autouse=True)
def configure_transcript_settings(monkeypatch):
    monkeypatch.setenv("YOUTUBE_TRANSCRIPT_API_KEY", "test-key")
    monkeypatch.setenv("YOUTUBE_TRANSCRIPT_MAX_RETRIES", "0")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class FakeResponse:
    def __init__(self, *, status_code: int, payload):
        self.status_code = status_code
        self._payload = payload
        self.text = str(payload)

    def json(self):
        return self._payload


def test_transcript_service_classifies_blocked_errors(monkeypatch):
    def fake_post(*_args, **_kwargs):
        return FakeResponse(
            status_code=429,
            payload={"error": {"code": "rate_limit_exceeded", "message": "Too many requests"}},
        )

    monkeypatch.setattr("httpx.post", fake_post)
    service = TranscriptService()
    with pytest.raises(TranscriptBlockedError):
        service.fetch_transcript(youtube_video_id="video123", preferred_languages=["en"])


def test_transcript_service_classifies_unavailable_errors(monkeypatch):
    def fake_post(*_args, **_kwargs):
        return FakeResponse(status_code=404, payload={"error": {"code": "no_captions", "message": "No captions"}})

    monkeypatch.setattr("httpx.post", fake_post)
    service = TranscriptService()
    with pytest.raises(TranscriptUnavailableError):
        service.fetch_transcript(youtube_video_id="video456", preferred_languages=["en"])


def test_transcript_service_classifies_provider_errors(monkeypatch):
    def fake_post(*_args, **_kwargs):
        return FakeResponse(status_code=500, payload={"error": {"code": "internal_error", "message": "boom"}})

    monkeypatch.setattr("httpx.post", fake_post)
    service = TranscriptService()
    with pytest.raises(TranscriptProviderError):
        service.fetch_transcript(youtube_video_id="video789", preferred_languages=["en"])


def test_transcript_service_returns_normalized_segments(monkeypatch):
    def fake_post(*_args, **_kwargs):
        return FakeResponse(
            status_code=200,
            payload={
                "status": "completed",
                "data": {
                    "transcript": {
                        "language": "en",
                        "text": "Welcome to this tutorial...",
                        "segments": [
                            {"text": "Welcome to this tutorial.", "start": 0, "end": 2500},
                            {"text": "Second line", "start": 2500, "end": 5000},
                        ],
                    }
                },
            },
        )

    monkeypatch.setattr("httpx.post", fake_post)
    service = TranscriptService()

    output = service.fetch_transcript(youtube_video_id="video000", preferred_languages=["en"])
    assert output.source_language == "en"
    assert len(output.segments) == 2
    assert output.segments[0]["timestamp"] == "00:00"
    assert output.segments[1]["timestamp"] == "00:02"
    assert "00:00 Welcome to this tutorial." in output.full_text


def test_transcript_service_classifies_asr_required_as_unavailable(monkeypatch):
    def fake_post(*_args, **_kwargs):
        return FakeResponse(
            status_code=200,
            payload={
                "status": "requires_asr_confirmation",
                "error": "No captions available. Audio transcription is required.",
                "suggestion": 'Use source="asr" or set allow_asr=true to enable ASR.',
            },
        )

    monkeypatch.setattr("httpx.post", fake_post)
    service = TranscriptService()

    with pytest.raises(TranscriptUnavailableError) as error:
        service.fetch_transcript(youtube_video_id="video-asr", preferred_languages=["en"])

    assert "requires ASR transcription" in str(error.value)


def test_transcript_service_falls_back_to_next_language_when_asr_required(monkeypatch):
    call_count = {"value": 0}

    def fake_post(*_args, **kwargs):
        call_count["value"] += 1
        payload = kwargs.get("json", {})
        requested_language = payload.get("language")
        if requested_language == "de":
            return FakeResponse(
                status_code=200,
                payload={
                    "status": "requires_asr_confirmation",
                    "error": "No captions available. Audio transcription is required.",
                    "suggestion": 'Use source="asr" or set allow_asr=true to enable ASR.',
                },
            )
        return FakeResponse(
            status_code=200,
            payload={
                "status": "completed",
                "data": {
                    "transcript": {
                        "language": "en",
                        "text": "Recovered transcript",
                        "segments": [
                            {"text": "Recovered transcript", "start": 0, "end": 2000},
                        ],
                    }
                },
            },
        )

    monkeypatch.setattr("httpx.post", fake_post)
    service = TranscriptService()

    output = service.fetch_transcript(youtube_video_id="video-fallback", preferred_languages=["de", "en"])
    assert output.source_language == "en"
    assert "Recovered transcript" in output.full_text
    assert call_count["value"] >= 2
