from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.enums import KnowledgeSourceStatus
from app.models.knowledge_base import KnowledgeBase
from app.models.knowledge_chunk import KnowledgeChunk
from app.models.knowledge_snapshot import KnowledgeSnapshot
from app.models.knowledge_source import KnowledgeSource


class KnowledgeRepository:
    def __init__(self, session: Session):
        self.session = session

    def create_base(self, *, monitor_profile_id: int, name: str, description: str, is_active: bool) -> KnowledgeBase:
        model = KnowledgeBase(
            monitor_profile_id=monitor_profile_id,
            name=name,
            description=description,
            is_active=is_active,
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return model

    def list_bases(self, *, monitor_profile_id: int) -> List[KnowledgeBase]:
        return (
            self.session.query(KnowledgeBase)
            .filter(KnowledgeBase.monitor_profile_id == monitor_profile_id)
            .order_by(KnowledgeBase.created_at.asc())
            .all()
        )

    def get_base(self, *, knowledge_base_id: int) -> Optional[KnowledgeBase]:
        return self.session.get(KnowledgeBase, knowledge_base_id)

    def get_active_base(self, *, monitor_profile_id: int) -> Optional[KnowledgeBase]:
        return (
            self.session.query(KnowledgeBase)
            .filter(KnowledgeBase.monitor_profile_id == monitor_profile_id, KnowledgeBase.is_active.is_(True))
            .order_by(KnowledgeBase.updated_at.desc())
            .first()
        )

    def set_active_base(self, *, monitor_profile_id: int, knowledge_base_id: int) -> None:
        self.session.query(KnowledgeBase).filter(KnowledgeBase.monitor_profile_id == monitor_profile_id).update(
            {KnowledgeBase.is_active: False}
        )
        self.session.query(KnowledgeBase).filter(
            KnowledgeBase.monitor_profile_id == monitor_profile_id,
            KnowledgeBase.id == knowledge_base_id,
        ).update({KnowledgeBase.is_active: True})
        self.session.commit()

    def save_base(self, model: KnowledgeBase) -> KnowledgeBase:
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return model

    def delete_base(self, *, knowledge_base_id: int) -> bool:
        model = self.get_base(knowledge_base_id=knowledge_base_id)
        if model is None:
            return False
        self.session.query(KnowledgeChunk).filter(KnowledgeChunk.knowledge_base_id == knowledge_base_id).delete()
        self.session.query(KnowledgeSource).filter(KnowledgeSource.knowledge_base_id == knowledge_base_id).delete()
        self.session.query(KnowledgeSnapshot).filter(KnowledgeSnapshot.knowledge_base_id == knowledge_base_id).delete()
        self.session.delete(model)
        self.session.commit()
        return True

    def create_source(
        self,
        *,
        monitor_profile_id: int,
        knowledge_base_id: int,
        source_type: str,
        title: str,
        uri_or_path: str,
        checksum: str,
        raw_text: str,
        status: KnowledgeSourceStatus,
        error_message: str = "",
    ) -> KnowledgeSource:
        model = KnowledgeSource(
            monitor_profile_id=monitor_profile_id,
            knowledge_base_id=knowledge_base_id,
            source_type=source_type,
            title=title,
            uri_or_path=uri_or_path,
            checksum=checksum,
            raw_text=raw_text,
            status=status,
            error_message=error_message,
        )
        self.session.add(model)
        self.session.commit()
        self.session.refresh(model)
        return model

    def list_sources(self, *, monitor_profile_id: int, knowledge_base_id: int) -> List[KnowledgeSource]:
        return (
            self.session.query(KnowledgeSource)
            .filter(
                KnowledgeSource.monitor_profile_id == monitor_profile_id,
                KnowledgeSource.knowledge_base_id == knowledge_base_id,
            )
            .order_by(KnowledgeSource.created_at.desc())
            .all()
        )

    def get_source(self, *, source_id: int) -> Optional[KnowledgeSource]:
        return self.session.get(KnowledgeSource, source_id)

    def get_source_by_checksum(self, *, knowledge_base_id: int, checksum: str) -> Optional[KnowledgeSource]:
        return (
            self.session.query(KnowledgeSource)
            .filter(KnowledgeSource.knowledge_base_id == knowledge_base_id, KnowledgeSource.checksum == checksum)
            .first()
        )

    def delete_source(self, *, source_id: int) -> bool:
        model = self.get_source(source_id=source_id)
        if model is None:
            return False
        self.session.query(KnowledgeChunk).filter(KnowledgeChunk.source_id == source_id).delete()
        self.session.delete(model)
        self.session.commit()
        return True

    def replace_chunks_for_source(self, *, source: KnowledgeSource, chunks: List[KnowledgeChunk]) -> None:
        self.session.query(KnowledgeChunk).filter(KnowledgeChunk.source_id == source.id).delete()
        for chunk in chunks:
            self.session.add(chunk)
        self.session.commit()

    def list_chunks_for_base(self, *, monitor_profile_id: int, knowledge_base_id: int) -> List[KnowledgeChunk]:
        return (
            self.session.query(KnowledgeChunk)
            .filter(
                KnowledgeChunk.monitor_profile_id == monitor_profile_id,
                KnowledgeChunk.knowledge_base_id == knowledge_base_id,
            )
            .order_by(KnowledgeChunk.source_id.asc(), KnowledgeChunk.chunk_order.asc())
            .all()
        )

    def upsert_snapshot(
        self,
        *,
        monitor_profile_id: int,
        knowledge_base_id: int,
        knowledge_md: str,
        source_set_hash: str,
    ) -> KnowledgeSnapshot:
        existing = (
            self.session.query(KnowledgeSnapshot)
            .filter(
                KnowledgeSnapshot.monitor_profile_id == monitor_profile_id,
                KnowledgeSnapshot.knowledge_base_id == knowledge_base_id,
            )
            .first()
        )
        if existing is None:
            existing = KnowledgeSnapshot(
                monitor_profile_id=monitor_profile_id,
                knowledge_base_id=knowledge_base_id,
                knowledge_md=knowledge_md,
                source_set_hash=source_set_hash,
            )
        else:
            existing.knowledge_md = knowledge_md
            existing.source_set_hash = source_set_hash
        self.session.add(existing)
        self.session.commit()
        self.session.refresh(existing)
        return existing

    def get_snapshot(self, *, monitor_profile_id: int, knowledge_base_id: int) -> Optional[KnowledgeSnapshot]:
        return (
            self.session.query(KnowledgeSnapshot)
            .filter(
                KnowledgeSnapshot.monitor_profile_id == monitor_profile_id,
                KnowledgeSnapshot.knowledge_base_id == knowledge_base_id,
            )
            .first()
        )
