from __future__ import annotations

import logging
from pathlib import Path
from textwrap import dedent

logger = logging.getLogger(__name__)


class AgentSettingsService:
    MAX_CHARS = 20000

    def __init__(self, path: Path | None = None):
        self.path = path or Path(__file__).resolve().parents[2] / "AGENTS.md"

    @staticmethod
    def default_content() -> str:
        return dedent(
            """
            # Video Analysis Agent

            **Role**: Expert Video Content Strategist & Technical Reviewer

            **Primary Objective**:
            Analyze video content to provide a high-level summary, identify strengths (Goods), and pinpoint areas for improvement (Bads).

            **Output Requirements**:
            1. **Executive Summary**: A concise 3-4 sentence overview of the video's core message.
            2. **The "Goods" (Strengths)**:
               - List 3-5 specific points where the video excels (e.g., pacing, visual clarity, key insights).
               - Explain why these are effective.
            3. **The "Bads" (Weaknesses)**:
               - List 2-5 specific areas for improvement (e.g., audio quality, technical inaccuracies, filler content).
               - Provide a brief suggestion for how to fix each.
            4. **Key Takeaways**: A bulleted list of the most important information conveyed.

            **Tone & Style**:
            - Professional yet accessible.
            - Objective and data-driven.
            - Avoid generic praise; be specific to the visual and auditory cues in the video.
            """
        ).strip()

    def get_content(self) -> str:
        return self._load_or_default()

    def get_payload(self) -> dict:
        return {
            "content": self.get_content(),
            "default_content": self.default_content(),
            "max_chars": self.MAX_CHARS,
        }

    def save_content(self, content: str) -> str:
        normalized = self._validate_content(content)
        self._write_content(normalized)
        return normalized

    def reset_to_default(self) -> str:
        default_content = self.default_content()
        self._write_content(default_content)
        return default_content

    def _load_or_default(self) -> str:
        if not self.path.exists():
            return self.default_content()
        try:
            raw = self.path.read_text(encoding="utf-8")
        except OSError as error:
            logger.warning("Failed to read AGENTS.md at %s: %s", self.path, error)
            return self.default_content()
        normalized = raw.strip()
        if not normalized:
            return self.default_content()
        return normalized

    def _validate_content(self, content: str) -> str:
        normalized = str(content or "").strip()
        if not normalized:
            raise ValueError("Agent settings cannot be empty.")
        if len(normalized) > self.MAX_CHARS:
            raise ValueError(f"Agent settings exceed max length of {self.MAX_CHARS} characters.")
        return normalized

    def _write_content(self, content: str) -> None:
        text_to_write = f"{content}\n"
        temp_path = self.path.with_suffix(".tmp")
        try:
            temp_path.write_text(text_to_write, encoding="utf-8")
            temp_path.replace(self.path)
        except OSError as error:
            raise ValueError("Failed to persist AGENTS.md settings.") from error
