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
