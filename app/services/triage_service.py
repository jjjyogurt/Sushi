from typing import Dict, List
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.monitor_repository import MonitorRepository
from app.repositories.video_repository import VideoRepository
from app.services.relevance_service import RelevanceService
from app.services.types import DiscoveredVideo
from app.services.youtube_discovery_service import YouTubeDiscoveryService
from app.utils.youtube import extract_video_id, fetch_oembed_metadata


class TriageService:
    def __init__(self, session: Session):
        self.analysis_repository = AnalysisRepository(session)
        self.audit_repository = AuditRepository(session)
        self.monitor_repository = MonitorRepository(session)
        self.video_repository = VideoRepository(session)
        self.relevance_service = RelevanceService()
        self.discovery_service = YouTubeDiscoveryService()

    def _require_profile(self, monitor_profile_id: int):
        profile = self.monitor_repository.get(monitor_profile_id)
        if profile is None:
            raise ValueError("Monitor profile not found.")
        return profile

    def _upsert_owned_video(
        self,
        *,
        monitor_profile_id: int,
        discovered_video: DiscoveredVideo,
        relevance_score: float,
        relevance_reason: str,
        raise_on_conflict: bool,
    ):
        existing = self.video_repository.get_by_youtube_id(discovered_video.youtube_video_id)
        if existing is not None and existing.monitor_profile_id != monitor_profile_id:
            error_message = (
                f"Video already belongs to project #{existing.monitor_profile_id}. "
                "A video can only belong to one project."
            )
            if raise_on_conflict:
                raise ValueError(error_message)
            return None

        return self.video_repository.upsert_candidate(
            monitor_profile_id=monitor_profile_id,
            youtube_video_id=discovered_video.youtube_video_id,
            video_url=discovered_video.video_url,
            title=discovered_video.title,
            channel_name=discovered_video.channel_name,
            language=discovered_video.language,
            published_at=discovered_video.published_at,
            relevance_score=relevance_score,
            relevance_reason=relevance_reason,
        )

    def get_monitor_profile_names_for_videos(self, videos) -> Dict[int, str]:
        profile_ids = list({video.monitor_profile_id for video in videos})
        profiles = self.monitor_repository.list_by_ids(profile_ids)
        return {profile.id: profile.name for profile in profiles}

    def get_sentiment_labels_for_videos(self, videos) -> Dict[int, str]:
        video_ids = [video.id for video in videos]
        return self.analysis_repository.get_latest_sentiment_by_video_ids(video_ids)

    def get_analysis_statuses_for_videos(self, videos) -> Dict[int, str]:
        video_ids = [video.id for video in videos]
        return self.analysis_repository.get_latest_status_by_video_ids(video_ids)

    def discover_for_profile(self, *, monitor_profile_id: int, max_results: int):
        profile = self._require_profile(monitor_profile_id)

        keywords = self.monitor_repository.unpack_keywords(profile)
        discovered = self.discovery_service.discover(profile=profile, max_results=max_results)
        persisted = []
        for item in discovered:
            relevance_score, relevance_reason = self.relevance_service.score(
                title=item.title,
                description=item.description,
                keywords=keywords,
            )
            candidate = self._upsert_owned_video(
                monitor_profile_id=monitor_profile_id,
                discovered_video=item,
                relevance_score=relevance_score,
                relevance_reason=relevance_reason,
                raise_on_conflict=False,
            )
            if candidate is not None:
                persisted.append(candidate)
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

    def search_candidates(self, *, monitor_profile_id: int, query: str, max_results: int) -> List[dict]:
        profile = self._require_profile(monitor_profile_id)

        profile_keywords = self.monitor_repository.unpack_keywords(profile)
        query_keywords = [item.strip() for item in query.split(",") if item.strip()]
        if not query_keywords:
            raise ValueError("At least one keyword is required for search.")

        languages = self.monitor_repository.unpack_languages(profile)
        markets = self.monitor_repository.unpack_markets(profile)
        discovered = self.discovery_service.discover_by_keywords(
            keywords=query_keywords,
            languages=languages,
            markets=markets,
            max_results=max_results,
        )
        scoring_keywords = list(dict.fromkeys([*profile_keywords, *query_keywords]))

        candidates = []
        for item in discovered:
            relevance_score, relevance_reason = self.relevance_service.score(
                title=item.title,
                description=item.description,
                keywords=scoring_keywords,
            )
            existing = self.video_repository.get_by_youtube_id(item.youtube_video_id)
            if existing is None:
                can_add = True
                block_reason = None
            elif existing.monitor_profile_id == monitor_profile_id:
                can_add = False
                block_reason = "Already in this project"
            else:
                can_add = False
                block_reason = f"Already belongs to project #{existing.monitor_profile_id}"

            candidates.append(
                {
                    "youtube_video_id": item.youtube_video_id,
                    "video_url": item.video_url,
                    "title": item.title,
                    "channel_name": item.channel_name,
                    "language": item.language,
                    "published_at": item.published_at,
                    "description": item.description,
                    "relevance_score": relevance_score,
                    "relevance_reason": relevance_reason,
                    "can_add": can_add,
                    "block_reason": block_reason,
                }
            )
        return candidates

    def add_bulk_candidates(self, *, monitor_profile_id: int, candidates: List) -> List:
        profile = self._require_profile(monitor_profile_id)
        keywords = self.monitor_repository.unpack_keywords(profile)
        persisted = []
        for candidate in candidates:
            relevance_score, relevance_reason = self.relevance_service.score(
                title=candidate.title,
                description=candidate.description,
                keywords=keywords,
            )
            discovered_video = DiscoveredVideo(
                youtube_video_id=candidate.youtube_video_id,
                video_url=candidate.video_url,
                title=candidate.title,
                channel_name=candidate.channel_name,
                language=candidate.language,
                published_at=candidate.published_at,
                description=candidate.description,
            )
            persisted_candidate = self._upsert_owned_video(
                monitor_profile_id=monitor_profile_id,
                discovered_video=discovered_video,
                relevance_score=relevance_score,
                relevance_reason=relevance_reason,
                raise_on_conflict=True,
            )
            if persisted_candidate is not None:
                persisted.append(persisted_candidate)

        self.audit_repository.record(
            actor="marketing-user",
            action="bulk_add_candidates",
            resource_type="monitor_profile",
            resource_id=str(monitor_profile_id),
            details=f"added_count={len(persisted)}",
        )
        return persisted

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
        profile = self._require_profile(monitor_profile_id)

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
        discovered_video = DiscoveredVideo(
            youtube_video_id=video_id,
            video_url=canonical_url,
            title=metadata["title"],
            channel_name=metadata["channel_name"],
            language=selected_language,
            published_at=datetime.now(timezone.utc),
            description=metadata["title"],
        )
        candidate = self._upsert_owned_video(
            monitor_profile_id=monitor_profile_id,
            discovered_video=discovered_video,
            relevance_score=relevance_score,
            relevance_reason=relevance_reason,
            raise_on_conflict=True,
        )
        self.audit_repository.record(
            actor="marketing-user",
            action="manual_video_added",
            resource_type="video_candidate",
            resource_id=str(candidate.id),
            details=f"video_id={video_id}",
        )
        return candidate

