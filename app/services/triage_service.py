from typing import List
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.repositories.audit_repository import AuditRepository
from app.repositories.monitor_repository import MonitorRepository
from app.repositories.video_repository import VideoRepository
from app.services.relevance_service import RelevanceService
from app.services.youtube_discovery_service import YouTubeDiscoveryService
from app.utils.youtube import extract_video_id, fetch_oembed_metadata


class TriageService:
    def __init__(self, session: Session):
        self.audit_repository = AuditRepository(session)
        self.monitor_repository = MonitorRepository(session)
        self.video_repository = VideoRepository(session)
        self.relevance_service = RelevanceService()
        self.discovery_service = YouTubeDiscoveryService()

    def discover_for_profile(self, *, monitor_profile_id: int, max_results: int):
        profile = self.monitor_repository.get(monitor_profile_id)
        if profile is None:
            raise ValueError("Monitor profile not found.")

        keywords = self.monitor_repository.unpack_keywords(profile)
        discovered = self.discovery_service.discover(profile=profile, max_results=max_results)
        persisted = []
        for item in discovered:
            relevance_score, relevance_reason = self.relevance_service.score(
                title=item.title,
                description=item.description,
                keywords=keywords,
            )
            persisted.append(
                self.video_repository.upsert_candidate(
                    monitor_profile_id=monitor_profile_id,
                    youtube_video_id=item.youtube_video_id,
                    video_url=item.video_url,
                    title=item.title,
                    channel_name=item.channel_name,
                    language=item.language,
                    published_at=item.published_at,
                    relevance_score=relevance_score,
                    relevance_reason=relevance_reason,
                )
            )
        self.audit_repository.record(
            actor="system",
            action="discover_videos",
            resource_type="monitor_profile",
            resource_id=str(monitor_profile_id),
            details=f"discovered_count={len(persisted)}",
        )
        return persisted

    def list_candidates(self, *, monitor_profile_id: int = None, queue_state=None, title_filter: str = None):
        return self.video_repository.list(
            monitor_profile_id=monitor_profile_id,
            queue_state=queue_state,
            title_filter=title_filter,
        )

    def approve(self, *, video_id: int, approved: bool):
        candidate = self.video_repository.update_queue_state(video_id=video_id, approved=approved)
        if candidate is None:
            raise ValueError("Video candidate not found.")
        self.audit_repository.record(
            actor="marketing-user",
            action="approve_video" if approved else "reject_video",
            resource_type="video_candidate",
            resource_id=str(video_id),
        )
        return candidate

    def delete_video(self, *, video_id: int):
        success = self.video_repository.delete(video_id=video_id)
        if not success:
            raise ValueError("Video candidate not found.")
        self.audit_repository.record(
            actor="marketing-user",
            action="delete_video",
            resource_type="video_candidate",
            resource_id=str(video_id),
        )
        return True

    def add_manual_video(self, *, monitor_profile_id: int, video_url: str, language: str = None):
        profile = self.monitor_repository.get(monitor_profile_id)
        if profile is None:
            raise ValueError("Monitor profile not found.")

        video_id = extract_video_id(video_url)
        canonical_url = f"https://www.youtube.com/watch?v={video_id}"
        metadata = fetch_oembed_metadata(canonical_url)

        keywords = self.monitor_repository.unpack_keywords(profile)
        relevance_score, relevance_reason = self.relevance_service.score(
            title=metadata["title"],
            description=metadata["title"],
            keywords=keywords,
        )
        selected_language = language or (self.monitor_repository.unpack_languages(profile) or ["en"])[0]
        candidate = self.video_repository.upsert_candidate(
            monitor_profile_id=monitor_profile_id,
            youtube_video_id=video_id,
            video_url=canonical_url,
            title=metadata["title"],
            channel_name=metadata["channel_name"],
            language=selected_language,
            published_at=datetime.now(timezone.utc),
            relevance_score=relevance_score,
            relevance_reason=relevance_reason,
        )
        self.audit_repository.record(
            actor="marketing-user",
            action="manual_video_added",
            resource_type="video_candidate",
            resource_id=str(candidate.id),
            details=f"video_id={video_id}",
        )
        return candidate

