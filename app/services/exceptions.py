class GeminiError(RuntimeError):
    """Base class for Gemini integration failures."""


class GeminiConfigurationError(GeminiError):
    """Raised when required Gemini configuration is missing."""


class GeminiDependencyError(GeminiError):
    """Raised when Gemini SDK dependencies are unavailable."""


class GeminiProviderError(GeminiError):
    """Raised when the Gemini provider request fails."""


class GeminiResponseError(GeminiError):
    """Raised when Gemini returns malformed or unusable output."""


class TranscriptError(RuntimeError):
    """Base class for transcript retrieval failures."""


class TranscriptBlockedError(TranscriptError):
    """Raised when transcript provider blocks requests from current network/IP."""


class TranscriptUnavailableError(TranscriptError):
    """Raised when transcripts are unavailable for the target video."""


class TranscriptProviderError(TranscriptError):
    """Raised when transcript provider returns an unexpected failure."""


class VideoProjectConflictError(ValueError):
    """Raised when a YouTube video is already owned by a different monitor profile."""

    def __init__(
        self,
        message: str,
        *,
        existing_video_id: int,
        existing_monitor_profile_id: int,
    ):
        super().__init__(message)
        self.existing_video_id = existing_video_id
        self.existing_monitor_profile_id = existing_monitor_profile_id
