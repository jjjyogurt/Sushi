from __future__ import annotations

import hashlib
from dataclasses import dataclass
from textwrap import dedent

from sqlalchemy.orm import Session

from app.models.agent_setting import AgentSetting


@dataclass(frozen=True)
class ResolvedAgentSettings:
    content: str
    settings_hash: str
    is_default: bool


class AgentSettingsService:
    MAX_CHARS = 20000

    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def default_content() -> str:
        return dedent(
            """
            # Influencer Video Reviewer & Product Marketing Agent

            Analyze influencer videos for consumer electronics product and marketing teams.

            Focus on:
            - Overall sentiment and evidence-based risk.
            - Concrete praise and criticism tied to on-camera evidence.
            - Technical failures, safety issues, repeatable problems, and competitor wins.
            - Tactical marketing response guidance.

            Use a concise, alert-oriented tone. Avoid generic commentary. Do not fabricate timestamps,
            incidents, product comparisons, or failure modes.
            """
        ).strip()

    @classmethod
    def hash_content(cls, content: str) -> str:
        normalized = cls._normalize_content(content)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def get_resolved(self, *, user_id: str) -> ResolvedAgentSettings:
        model = self.session.get(AgentSetting, user_id)
        if model is None:
            default_content = self.default_content()
            return ResolvedAgentSettings(
                content=default_content,
                settings_hash=self.hash_content(default_content),
                is_default=True,
            )
        return ResolvedAgentSettings(
            content=model.content,
            settings_hash=model.settings_hash,
            is_default=False,
        )

    def get_payload(self, *, user_id: str) -> dict:
        resolved = self.get_resolved(user_id=user_id)
        return {
            "content": resolved.content,
            "settings_hash": resolved.settings_hash,
            "is_default": resolved.is_default,
            "default_content": self.default_content(),
            "max_chars": self.MAX_CHARS,
        }

    def save_content(self, *, user_id: str, content: str) -> str:
        normalized = self._validate_content(content)
        settings_hash = self.hash_content(normalized)
        model = self.session.get(AgentSetting, user_id)
        if model is None:
            model = AgentSetting(user_id=user_id, content=normalized, settings_hash=settings_hash)
        else:
            model.content = normalized
            model.settings_hash = settings_hash
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return normalized

    def reset_to_default(self, *, user_id: str) -> str:
        return self.save_content(user_id=user_id, content=self.default_content())

    @classmethod
    def _validate_content(cls, content: str) -> str:
        normalized = cls._normalize_content(content)
        if not normalized:
            raise ValueError("Agent settings cannot be empty.")
        if len(normalized) > cls.MAX_CHARS:
            raise ValueError(f"Agent settings exceed max length of {cls.MAX_CHARS} characters.")
        return normalized

    @staticmethod
    def _normalize_content(content: str) -> str:
        return str(content or "").strip()
