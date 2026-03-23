import sys
import types

import pytest

from app.services.exceptions import (
    TranscriptBlockedError,
    TranscriptProviderError,
    TranscriptUnavailableError,
)
from app.services.transcript_service import TranscriptService


def install_fake_transcript_module(monkeypatch, api_class):
    fake_module = types.ModuleType("youtube_transcript_api")
    fake_module.YouTubeTranscriptApi = api_class
    monkeypatch.setitem(sys.modules, "youtube_transcript_api", fake_module)


class BlockingApi:
    def list(self, _youtube_video_id):
        raise Exception("YouTube is blocking requests from your IP due to too many requests")


class UnavailableTranscriptList:
    def find_transcript(self, _languages):
        raise Exception("No transcript available")

    def find_generated_transcript(self, _languages):
        raise Exception("No generated transcript available")

    def __iter__(self):
        return iter([])


class UnavailableApi:
    def list(self, _youtube_video_id):
        return UnavailableTranscriptList()


class ProviderFailureApi:
    def list(self, _youtube_video_id):
        raise Exception("gateway timeout from transcript provider")


def test_transcript_service_classifies_blocked_errors(monkeypatch):
    install_fake_transcript_module(monkeypatch, BlockingApi)
    service = TranscriptService()
    with pytest.raises(TranscriptBlockedError):
        service.fetch_transcript(youtube_video_id="video123", preferred_languages=["en"])


def test_transcript_service_classifies_unavailable_errors(monkeypatch):
    install_fake_transcript_module(monkeypatch, UnavailableApi)
    service = TranscriptService()
    with pytest.raises(TranscriptUnavailableError):
        service.fetch_transcript(youtube_video_id="video456", preferred_languages=["en"])


def test_transcript_service_classifies_provider_errors(monkeypatch):
    install_fake_transcript_module(monkeypatch, ProviderFailureApi)
    service = TranscriptService()
    with pytest.raises(TranscriptProviderError):
        service.fetch_transcript(youtube_video_id="video789", preferred_languages=["en"])
