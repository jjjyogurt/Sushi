from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from urllib.error import URLError
from urllib.request import Request, urlopen

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.models.enums import KnowledgeSourceStatus
from app.models.knowledge_chunk import KnowledgeChunk
from app.repositories.knowledge_repository import KnowledgeRepository
from app.repositories.monitor_repository import MonitorRepository


@dataclass(frozen=True)
class KnowledgeChunkInput:
    text: str
    chunk_order: int
    token_count: int


class KnowledgeIngestionService:
    MAX_SOURCE_CHARS = 120_000
    MAX_FILE_BYTES = 3 * 1024 * 1024
    MAX_KB_NAME_CHARS = 120
    ALLOWED_EXTENSIONS = {".md", ".txt", ".csv", ".json"}

    def __init__(self, session: Session):
        self.repository = KnowledgeRepository(session)
        self.monitor_repository = MonitorRepository(session)

    def list_bases(self, *, monitor_profile_id: int):
        self._require_profile(monitor_profile_id=monitor_profile_id)
        return self.repository.list_bases(monitor_profile_id=monitor_profile_id)

    def create_base(self, *, monitor_profile_id: int, name: str, description: str = ""):
        self._require_profile(monitor_profile_id=monitor_profile_id)
        normalized_name = self._normalize_base_name(name)
        self._assert_unique_name(monitor_profile_id=monitor_profile_id, normalized_name=normalized_name)
        existing = self.repository.list_bases(monitor_profile_id=monitor_profile_id)
        return self.repository.create_base(
            monitor_profile_id=monitor_profile_id,
            name=normalized_name,
            description=description.strip(),
            is_active=len(existing) == 0,
        )

    def update_base(
        self,
        *,
        knowledge_base_id: int,
        name: str | None,
        is_active: bool | None,
        description: str | None,
    ):
        kb = self.repository.get_base(knowledge_base_id=knowledge_base_id)
        if kb is None:
            raise ValueError("Knowledge base not found.")

        if name is not None:
            normalized_name = self._normalize_base_name(name)
            if normalized_name.lower() != kb.name.lower():
                self._assert_unique_name(monitor_profile_id=kb.monitor_profile_id, normalized_name=normalized_name)
            kb.name = normalized_name
        if description is not None:
            kb.description = description.strip()

        saved = self.repository.save_base(kb)
        if is_active is True:
            self.repository.set_active_base(monitor_profile_id=saved.monitor_profile_id, knowledge_base_id=saved.id)
            saved = self.repository.get_base(knowledge_base_id=saved.id)
        return saved

    def delete_base(self, *, knowledge_base_id: int):
        kb = self.repository.get_base(knowledge_base_id=knowledge_base_id)
        if kb is None:
            raise ValueError("Knowledge base not found.")
        monitor_profile_id = kb.monitor_profile_id
        deleted = self.repository.delete_base(knowledge_base_id=knowledge_base_id)
        if not deleted:
            raise ValueError("Knowledge base not found.")
        remaining = self.repository.list_bases(monitor_profile_id=monitor_profile_id)
        if remaining and not any(item.is_active for item in remaining):
            self.repository.set_active_base(monitor_profile_id=monitor_profile_id, knowledge_base_id=remaining[0].id)

    def list_sources(self, *, monitor_profile_id: int, knowledge_base_id: int):
        self._require_kb_scope(monitor_profile_id=monitor_profile_id, knowledge_base_id=knowledge_base_id)
        return self.repository.list_sources(monitor_profile_id=monitor_profile_id, knowledge_base_id=knowledge_base_id)

    async def add_file_source(self, *, monitor_profile_id: int, knowledge_base_id: int, upload: UploadFile):
        kb = self._require_kb_scope(monitor_profile_id=monitor_profile_id, knowledge_base_id=knowledge_base_id)
        filename = str(upload.filename or "").strip() or "uploaded-file.txt"
        self._validate_file_extension(filename)
        payload = await upload.read()
        if not payload:
            raise ValueError("Uploaded file is empty.")
        if len(payload) > self.MAX_FILE_BYTES:
            raise ValueError("Uploaded file is too large.")
        text = payload.decode("utf-8", errors="ignore").strip()
        if not text:
            raise ValueError("Unable to extract readable text from uploaded file.")
        text = text[: self.MAX_SOURCE_CHARS]
        checksum = hashlib.sha256(payload).hexdigest()
        existing = self.repository.get_source_by_checksum(knowledge_base_id=knowledge_base_id, checksum=checksum)
        if existing is not None:
            return existing

        source = self.repository.create_source(
            monitor_profile_id=monitor_profile_id,
            knowledge_base_id=knowledge_base_id,
            source_type="file",
            title=filename,
            uri_or_path=filename,
            checksum=checksum,
            raw_text=text,
            status=KnowledgeSourceStatus.PROCESSING,
        )
        self._index_source(source_id=source.id, monitor_profile_id=monitor_profile_id, knowledge_base_id=kb.id)
        return self.repository.get_source(source_id=source.id)

    def add_url_source(self, *, monitor_profile_id: int, knowledge_base_id: int, url: str, title: str = ""):
        kb = self._require_kb_scope(monitor_profile_id=monitor_profile_id, knowledge_base_id=knowledge_base_id)
        normalized_url = str(url or "").strip()
        if not normalized_url.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")

        text = self._fetch_url_text(normalized_url)
        checksum = hashlib.sha256(text.encode("utf-8")).hexdigest()
        existing = self.repository.get_source_by_checksum(knowledge_base_id=knowledge_base_id, checksum=checksum)
        if existing is not None:
            return existing

        source = self.repository.create_source(
            monitor_profile_id=monitor_profile_id,
            knowledge_base_id=knowledge_base_id,
            source_type="url",
            title=title.strip() or normalized_url,
            uri_or_path=normalized_url,
            checksum=checksum,
            raw_text=text,
            status=KnowledgeSourceStatus.PROCESSING,
        )
        self._index_source(source_id=source.id, monitor_profile_id=monitor_profile_id, knowledge_base_id=kb.id)
        return self.repository.get_source(source_id=source.id)

    def delete_source(self, *, source_id: int):
        deleted = self.repository.delete_source(source_id=source_id)
        if not deleted:
            raise ValueError("Knowledge source not found.")

    def get_summary(self, *, monitor_profile_id: int, knowledge_base_id: int) -> str:
        self._require_kb_scope(monitor_profile_id=monitor_profile_id, knowledge_base_id=knowledge_base_id)
        snapshot = self.repository.get_snapshot(monitor_profile_id=monitor_profile_id, knowledge_base_id=knowledge_base_id)
        if snapshot is None:
            return ""
        return snapshot.knowledge_md

    def _require_profile(self, *, monitor_profile_id: int):
        profile = self.monitor_repository.get(monitor_profile_id)
        if profile is None:
            raise ValueError("Monitor profile not found.")
        return profile

    def _require_kb_scope(self, *, monitor_profile_id: int, knowledge_base_id: int):
        self._require_profile(monitor_profile_id=monitor_profile_id)
        kb = self.repository.get_base(knowledge_base_id=knowledge_base_id)
        if kb is None or kb.monitor_profile_id != monitor_profile_id:
            raise ValueError("Knowledge base not found for this project.")
        return kb

    def _assert_unique_name(self, *, monitor_profile_id: int, normalized_name: str) -> None:
        existing = self.repository.list_bases(monitor_profile_id=monitor_profile_id)
        if any(item.name.lower() == normalized_name.lower() for item in existing):
            raise ValueError("Knowledge base name already exists for this project.")

    def _normalize_base_name(self, value: str) -> str:
        normalized = str(value or "").strip()
        if not normalized:
            raise ValueError("Knowledge base name cannot be empty.")
        if len(normalized) > self.MAX_KB_NAME_CHARS:
            raise ValueError(f"Knowledge base name must be <= {self.MAX_KB_NAME_CHARS} characters.")
        return normalized

    def _index_source(self, *, source_id: int, monitor_profile_id: int, knowledge_base_id: int) -> None:
        source = self.repository.get_source(source_id=source_id)
        if source is None:
            raise ValueError("Knowledge source not found.")
        if source.monitor_profile_id != monitor_profile_id or source.knowledge_base_id != knowledge_base_id:
            raise ValueError("Knowledge source scope mismatch.")
        try:
            prepared_chunks = self._chunk_text(source.raw_text)
            chunk_models = [
                KnowledgeChunk(
                    source_id=source.id,
                    monitor_profile_id=monitor_profile_id,
                    knowledge_base_id=knowledge_base_id,
                    chunk_order=item.chunk_order,
                    chunk_text=item.text,
                    token_count=item.token_count,
                    metadata_json="{}",
                )
                for item in prepared_chunks
            ]
            self.repository.replace_chunks_for_source(source=source, chunks=chunk_models)
            source.status = KnowledgeSourceStatus.READY
            source.error_message = ""
            self.repository.session.add(source)
            self.repository.session.commit()
            self.repository.session.refresh(source)
        except Exception as error:  # noqa: BLE001
            source.status = KnowledgeSourceStatus.FAILED
            source.error_message = str(error)
            self.repository.session.add(source)
            self.repository.session.commit()
            self.repository.session.refresh(source)
        self._refresh_snapshot(monitor_profile_id=monitor_profile_id, knowledge_base_id=knowledge_base_id)

    def _refresh_snapshot(self, *, monitor_profile_id: int, knowledge_base_id: int) -> None:
        sources = self.repository.list_sources(monitor_profile_id=monitor_profile_id, knowledge_base_id=knowledge_base_id)
        ready_sources = [source for source in sources if source.status == KnowledgeSourceStatus.READY and source.raw_text.strip()]
        source_hash_seed = "|".join(sorted(source.checksum for source in ready_sources))
        source_set_hash = hashlib.sha256(source_hash_seed.encode("utf-8")).hexdigest() if source_hash_seed else ""
        knowledge_md = self._build_knowledge_markdown(ready_sources=ready_sources)
        self.repository.upsert_snapshot(
            monitor_profile_id=monitor_profile_id,
            knowledge_base_id=knowledge_base_id,
            knowledge_md=knowledge_md,
            source_set_hash=source_set_hash,
        )

    def _chunk_text(self, text: str) -> list[KnowledgeChunkInput]:
        normalized = self._normalize_text(text)
        if not normalized:
            return []
        max_chars = 1200
        parts = []
        current = []
        current_chars = 0
        for line in normalized.splitlines():
            striped = line.strip()
            if not striped:
                continue
            candidate_size = current_chars + len(striped) + (1 if current else 0)
            if current and candidate_size > max_chars:
                joined = "\n".join(current)
                parts = [
                    *parts,
                    KnowledgeChunkInput(text=joined, chunk_order=len(parts), token_count=max(1, len(joined.split()))),
                ]
                current = [striped]
                current_chars = len(striped)
                continue
            current = [*current, striped]
            current_chars = candidate_size
        if current:
            joined = "\n".join(current)
            parts = [*parts, KnowledgeChunkInput(text=joined, chunk_order=len(parts), token_count=max(1, len(joined.split())))]
        return parts

    def _build_knowledge_markdown(self, *, ready_sources) -> str:
        if not ready_sources:
            return "# Knowledge Base Summary\n\nNo indexed sources yet."
        lines = ["# Knowledge Base Summary", ""]
        for source in ready_sources[:10]:
            lines.append(f"## {source.title}")
            lines.append(f"- Source: {source.source_type}")
            if source.uri_or_path:
                lines.append(f"- Location: {source.uri_or_path}")
            excerpt = self._first_sentences(source.raw_text, sentence_count=3)
            lines.append("- Highlights:")
            for sentence in excerpt:
                lines.append(f"  - {sentence}")
            lines.append("")
        return "\n".join(lines).strip()

    @staticmethod
    def _first_sentences(text: str, sentence_count: int) -> list[str]:
        normalized = " ".join(text.split())
        if not normalized:
            return []
        parts = re.split(r"(?<=[.!?])\s+", normalized)
        return [item.strip() for item in parts[:sentence_count] if item.strip()]

    def _fetch_url_text(self, url: str) -> str:
        request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
        try:
            with urlopen(request, timeout=12) as response:
                payload = response.read(self.MAX_FILE_BYTES + 1)
        except URLError as error:
            raise ValueError(f"Failed to fetch URL: {error}") from error
        if len(payload) > self.MAX_FILE_BYTES:
            raise ValueError("Fetched URL content is too large.")
        decoded = payload.decode("utf-8", errors="ignore")
        cleaned = self._normalize_text(decoded)
        if not cleaned:
            raise ValueError("Fetched URL has no readable content.")
        return cleaned[: self.MAX_SOURCE_CHARS]

    def _normalize_text(self, raw_text: str) -> str:
        text = str(raw_text or "")
        text = re.sub(r"<script[^>]*>.*?</script>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.IGNORECASE | re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = html.unescape(text)
        text = re.sub(r"\r\n?", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]{2,}", " ", text)
        return text.strip()

    def _validate_file_extension(self, filename: str) -> None:
        lowered = filename.lower()
        if any(lowered.endswith(extension) for extension in self.ALLOWED_EXTENSIONS):
            return
        accepted = ", ".join(sorted(self.ALLOWED_EXTENSIONS))
        raise ValueError(f"Unsupported file type. Allowed extensions: {accepted}")
