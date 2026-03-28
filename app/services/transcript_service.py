import json
import logging
from statistics import median
from typing import Dict, List, Optional

import httpx

from app.config import get_settings
from app.services.exceptions import (
    TranscriptBlockedError,
    TranscriptProviderError,
    TranscriptUnavailableError,
)
from app.services.types import TranscriptOutput

logger = logging.getLogger(__name__)


class TranscriptService:
    def __init__(self):
        self.settings = get_settings()

    def fetch_transcript(self, *, youtube_video_id: str, preferred_languages: List[str]) -> TranscriptOutput:
        api_key = self.settings.youtube_transcript_api_key.strip()
        if not api_key:
            raise TranscriptProviderError("YOUTUBE_TRANSCRIPT_API_KEY is not configured.")
        language_candidates = [lang.strip() for lang in preferred_languages if lang.strip()]
        language_candidates = language_candidates or ["en"]
        last_unavailable_error: Optional[TranscriptUnavailableError] = None
        for language in language_candidates:
            try:
                return self._fetch_from_provider(youtube_video_id=youtube_video_id, language=language, api_key=api_key)
            except TranscriptUnavailableError as error:
                logger.info(
                    "transcript unavailable video_id=%s language=%s error=%s",
                    youtube_video_id,
                    language,
                    error,
                )
                last_unavailable_error = error
                continue

        try:
            return self._fetch_from_provider(youtube_video_id=youtube_video_id, language=None, api_key=api_key)
        except TranscriptUnavailableError as error:
            logger.info(
                "transcript unavailable fallback video_id=%s language=%s error=%s",
                youtube_video_id,
                "auto",
                error,
            )
            raise last_unavailable_error or error from error

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        total = max(0, int(seconds))
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def _fetch_from_provider(self, *, youtube_video_id: str, language: Optional[str], api_key: str) -> TranscriptOutput:
        payload: Dict[str, object] = {
            "video": youtube_video_id,
            "source": "auto",
            "allow_asr": False,
            "format": {"timestamp": True},
        }
        if language:
            payload["language"] = language

        url = f"{self.settings.youtube_transcript_base_url.rstrip('/')}/transcribe"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        max_retries = max(0, int(self.settings.youtube_transcript_max_retries))
        timeout = max(1.0, float(self.settings.youtube_transcript_timeout_seconds))

        last_transport_error: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            try:
                response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
            except (httpx.TimeoutException, httpx.TransportError) as error:
                last_transport_error = error
                if attempt < max_retries:
                    continue
                break

            if response.status_code >= 400:
                error_payload = self._parse_json(response)
                raise self._classify_provider_error(
                    youtube_video_id=youtube_video_id,
                    status_code=response.status_code,
                    payload=error_payload,
                    fallback=response.text,
                )

            response_payload = self._parse_json(response)
            provider_status = str(response_payload.get("status") or "").strip().lower()
            logger.info(
                "transcript provider response video_id=%s language=%s http_status=%s provider_status=%s",
                youtube_video_id,
                language or "auto",
                response.status_code,
                provider_status or "unknown",
            )
            self._raise_for_non_completed_success(
                youtube_video_id=youtube_video_id,
                language=language,
                payload=response_payload,
            )
            return self._build_transcript_output(youtube_video_id=youtube_video_id, payload=response_payload)

        error_message = str(last_transport_error) if last_transport_error is not None else "unknown transport error"
        raise TranscriptProviderError(
            f"Failed to retrieve transcript for video {youtube_video_id}: {error_message}"
        )

    @staticmethod
    def _raise_for_non_completed_success(
        *, youtube_video_id: str, language: Optional[str], payload: Dict[str, object]
    ) -> None:
        status_value = str(payload.get("status") or "").strip().lower()
        if not status_value or status_value == "completed":
            return

        error_message = str(payload.get("error") or "").strip()
        suggestion = str(payload.get("suggestion") or "").strip()
        context_parts = [part for part in [error_message, suggestion] if part]
        context = f" Details: {' '.join(context_parts)}" if context_parts else ""
        language_hint = language or "auto"

        if status_value == "requires_asr_confirmation":
            raise TranscriptUnavailableError(
                f"No transcript is available for video {youtube_video_id} in language '{language_hint}'."
                f" Provider requires ASR transcription before analysis.{context}"
            )

        if status_value in {"no_captions", "not_found", "unavailable"}:
            raise TranscriptUnavailableError(
                f"No transcript is available for video {youtube_video_id} in language '{language_hint}'.{context}"
            )

        raise TranscriptProviderError(
            f"Transcript provider returned status '{status_value}' for video {youtube_video_id} in language "
            f"'{language_hint}'.{context}"
        )

    @staticmethod
    def _parse_json(response: httpx.Response) -> Dict[str, object]:
        try:
            payload = response.json()
        except json.JSONDecodeError as error:
            raise TranscriptProviderError("Transcript provider returned non-JSON response.") from error
        if not isinstance(payload, dict):
            raise TranscriptProviderError("Transcript provider returned malformed payload.")
        return payload

    def _build_transcript_output(self, *, youtube_video_id: str, payload: Dict[str, object]) -> TranscriptOutput:
        data = payload.get("data")
        if not isinstance(data, dict):
            raise TranscriptProviderError(f"Malformed transcript payload for video {youtube_video_id}: missing data.")
        transcript = data.get("transcript")
        if not isinstance(transcript, dict):
            raise TranscriptProviderError(
                f"Malformed transcript payload for video {youtube_video_id}: missing transcript."
            )

        transcript_text = str(transcript.get("text") or "").strip()
        segments_raw = transcript.get("segments")
        segments_list = segments_raw if isinstance(segments_raw, list) else []

        use_milliseconds = self._segments_use_milliseconds(segments_list)
        segments = self._normalize_segments(segments_list=segments_list, use_milliseconds=use_milliseconds)

        if not segments and transcript_text:
            segments = [{"timestamp": "00:00", "text": transcript_text.replace("\n", " ").strip(), "duration": 0.0}]
        if not segments:
            raise TranscriptUnavailableError(f"No transcript is available for video {youtube_video_id} in requested languages.")

        full_text = "\n".join(f"{item['timestamp']} {item['text']}" for item in segments)
        source_language = str(transcript.get("language") or "en")
        return TranscriptOutput(full_text=full_text, segments=segments, source_language=source_language)

    def _normalize_segments(self, *, segments_list: List[object], use_milliseconds: bool) -> List[Dict[str, object]]:
        divisor = 1000.0 if use_milliseconds else 1.0
        normalized: List[Dict[str, object]] = []
        for item in segments_list:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text") or "").replace("\n", " ").strip()
            if not text:
                continue
            start = self._to_float(item.get("start"), default=0.0)
            end = self._to_float(item.get("end"), default=start)
            duration = max(0.0, (end - start) / divisor)
            normalized.append(
                {
                    "timestamp": self._format_timestamp(start / divisor),
                    "text": text,
                    "duration": duration,
                }
            )
        return normalized

    @staticmethod
    def _to_float(value: object, *, default: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _segments_use_milliseconds(segments_list: List[object]) -> bool:
        durations: List[float] = []
        for item in segments_list[:20]:
            if not isinstance(item, dict):
                continue
            start = item.get("start")
            end = item.get("end")
            try:
                start_float = float(start)
                end_float = float(end)
            except (TypeError, ValueError):
                continue
            delta = end_float - start_float
            if delta > 0:
                durations.append(delta)
        if not durations:
            return False
        return median(durations) > 60

    @staticmethod
    def _classify_provider_error(
        *, youtube_video_id: str, status_code: int, payload: Dict[str, object], fallback: str
    ) -> RuntimeError:
        error_payload = payload.get("error")
        error_code = ""
        message = fallback
        if isinstance(error_payload, dict):
            error_code = str(error_payload.get("code") or "").strip().lower()
            message = str(error_payload.get("message") or fallback)

        if status_code == 429 or error_code == "rate_limit_exceeded":
            return TranscriptBlockedError(
                f"Transcript provider rate-limited requests for video {youtube_video_id}. Retry later."
            )
        if status_code == 404 or error_code == "no_captions":
            return TranscriptUnavailableError(
                f"No transcript is available for video {youtube_video_id} in requested languages."
            )
        return TranscriptProviderError(f"Failed to retrieve transcript for video {youtube_video_id}: {message}")

