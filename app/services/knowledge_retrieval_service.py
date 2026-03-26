import re
from typing import List, Optional

from sqlalchemy.orm import Session

from app.repositories.knowledge_repository import KnowledgeRepository


class KnowledgeRetrievalService:
    def __init__(self, session: Session):
        self.repository = KnowledgeRepository(session)

    def resolve_base_id(self, *, monitor_profile_id: int, knowledge_base_id: Optional[int]) -> Optional[int]:
        if knowledge_base_id is not None:
            kb = self.repository.get_base(knowledge_base_id=knowledge_base_id)
            if kb is None or kb.monitor_profile_id != monitor_profile_id:
                raise ValueError("Knowledge base not found for this project.")
            return kb.id
        active = self.repository.get_active_base(monitor_profile_id=monitor_profile_id)
        return active.id if active else None

    def build_knowledge_context(
        self,
        *,
        monitor_profile_id: int,
        query_text: str,
        knowledge_base_id: Optional[int] = None,
        max_chunks: int = 6,
        max_chars: int = 4000,
    ) -> str:
        resolved_base_id = self.resolve_base_id(
            monitor_profile_id=monitor_profile_id,
            knowledge_base_id=knowledge_base_id,
        )
        if resolved_base_id is None:
            return ""

        snapshot = self.repository.get_snapshot(monitor_profile_id=monitor_profile_id, knowledge_base_id=resolved_base_id)
        chunks = self.repository.list_chunks_for_base(
            monitor_profile_id=monitor_profile_id,
            knowledge_base_id=resolved_base_id,
        )
        if not chunks and not snapshot:
            return ""

        query_tokens = self._tokenize(query_text)
        ranked = sorted(chunks, key=lambda item: self._score(query_tokens=query_tokens, text=item.chunk_text), reverse=True)
        selected = [item for item in ranked if item.chunk_text.strip()][:max_chunks]

        sections: List[str] = []
        if snapshot and snapshot.knowledge_md:
            sections = [*sections, "Knowledge summary:", snapshot.knowledge_md.strip()]
        if selected:
            sections = [*sections, "Retrieved knowledge evidence:"]
            for chunk in selected:
                sections = [*sections, f"- [chunk:{chunk.id}] {chunk.chunk_text.strip()}"]

        assembled = "\n".join(sections).strip()
        if len(assembled) <= max_chars:
            return assembled
        return assembled[:max_chars].rstrip()

    @staticmethod
    def _tokenize(value: str) -> List[str]:
        return [token for token in re.findall(r"[a-z0-9]+", str(value).lower()) if len(token) > 2]

    @staticmethod
    def _score(*, query_tokens: List[str], text: str) -> int:
        lowered = text.lower()
        if not query_tokens:
            return 1
        overlap = sum(1 for token in query_tokens if token in lowered)
        prefix_bonus = 2 if any(token in lowered[:300] for token in query_tokens) else 0
        return overlap + prefix_bonus
