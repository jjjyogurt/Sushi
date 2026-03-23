def sanitize_transcript_context(transcript_text: str) -> str:
    blocked_fragments = [
        "ignore previous instructions",
        "system prompt",
        "developer message",
        "act as",
        "override safety",
    ]
    sanitized = transcript_text
    for fragment in blocked_fragments:
        sanitized = sanitized.replace(fragment, "[filtered]")
        sanitized = sanitized.replace(fragment.title(), "[filtered]")
    return sanitized

