from typing import List

from app.services.types import TranscriptOutput


class TranscriptService:
    def fetch_transcript(self, *, youtube_video_id: str, preferred_languages: List[str]) -> TranscriptOutput:
        try:
            from youtube_transcript_api import YouTubeTranscriptApi
        except ImportError as error:
            raise RuntimeError("youtube-transcript-api package is required for transcript extraction.") from error

        language_candidates = [lang.strip() for lang in preferred_languages if lang.strip()]
        language_candidates = language_candidates or ["en"]
        api = YouTubeTranscriptApi()

        try:
            transcript_list = api.list(youtube_video_id)
            transcript = self._select_transcript(transcript_list=transcript_list, language_candidates=language_candidates)
            segments_raw = transcript.fetch().to_raw_data()
        except Exception as error:  # noqa: BLE001
            raise RuntimeError(f"Failed to retrieve transcript for video {youtube_video_id}: {error}") from error

        if not segments_raw:
            raise RuntimeError(f"Transcript is empty for video {youtube_video_id}.")

        segments = [
            {
                "timestamp": self._format_timestamp(item.get("start", 0)),
                "text": (item.get("text") or "").replace("\n", " ").strip(),
                "duration": float(item.get("duration", 0)),
            }
            for item in segments_raw
            if (item.get("text") or "").strip()
        ]
        if not segments:
            raise RuntimeError(f"Transcript has no usable text for video {youtube_video_id}.")

        full_text = "\n".join(f"{item['timestamp']} {item['text']}" for item in segments)
        source_language = getattr(transcript, "language_code", language_candidates[0])
        return TranscriptOutput(full_text=full_text, segments=segments, source_language=source_language)

    @staticmethod
    def _select_transcript(*, transcript_list, language_candidates: List[str]):
        for lang in language_candidates:
            try:
                return transcript_list.find_transcript([lang])
            except Exception:  # noqa: BLE001
                continue

        for lang in language_candidates:
            try:
                return transcript_list.find_generated_transcript([lang])
            except Exception:  # noqa: BLE001
                continue

        try:
            available = list(transcript_list)
            if available:
                return available[0]
        except Exception as error:  # noqa: BLE001
            raise RuntimeError(f"No transcript available: {error}") from error

        raise RuntimeError("No transcript available in requested languages.")

    @staticmethod
    def _format_timestamp(seconds: float) -> str:
        total = max(0, int(seconds))
        hours, remainder = divmod(total, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

