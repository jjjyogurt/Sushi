import logging
import re
from typing import Dict, List, Optional
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.repositories.analysis_repository import AnalysisRepository
from app.repositories.app_user_repository import AppUserRepository
from app.repositories.audit_repository import AuditRepository
from app.repositories.monitor_repository import MonitorRepository
from app.repositories.video_repository import VideoRepository
from app.services.discovery_keyword_service import DiscoveryKeywordService
from app.services.gemini_client import GeminiClient
from app.services.relevance_service import RelevanceService
from app.services.types import DiscoveredVideo
from app.services.youtube_discovery_service import (
    YouTubeDiscoveryService,
    filter_discovered_videos_by_publish_window,
)
from app.utils.text import normalize_title
from app.utils.youtube import extract_video_id, fetch_oembed_metadata

logger = logging.getLogger(__name__)


class TriageService:
    def __init__(self, session: Session):
        self.analysis_repository = AnalysisRepository(session)
        self.app_user_repository = AppUserRepository(session)
        self.audit_repository = AuditRepository(session)
        self.monitor_repository = MonitorRepository(session)
        self.video_repository = VideoRepository(session)
        self.relevance_service = RelevanceService()
        self.discovery_service = YouTubeDiscoveryService()
        self.settings = get_settings()
        gemini_client = GeminiClient(self.settings) if self.settings.gemini_api_key.strip() else None
        self.discovery_keyword_service = DiscoveryKeywordService(self.settings, gemini_client)

    def _monitoring_keywords(self, profile) -> List[str]:
        keywords = self.monitor_repository.unpack_keywords(profile)
        key_products = self.monitor_repository.unpack_key_products(profile)
        return list(dict.fromkeys([*keywords, *key_products]))

    @staticmethod
    def _normalize_search_text(value: str) -> str:
        normalized = normalize_title(value or "")
        alnum_only = re.sub(r"[\W_]+", " ", normalized, flags=re.UNICODE)
        collapsed = re.sub(r"\s+", " ", alnum_only, flags=re.UNICODE)
        return collapsed.strip()

    @staticmethod
    def _contains_non_ascii(value: str) -> bool:
        return any(ord(character) > 127 for character in str(value or ""))

    def _keyword_matches_title(self, *, normalized_title: str, keyword: str) -> bool:
        normalized_keyword = self._normalize_search_text(keyword)
        if not normalized_keyword:
            return False
        if self._contains_non_ascii(normalized_keyword):
            return normalized_keyword in normalized_title
        pattern = r"\b" + r"\s+".join(re.escape(token) for token in normalized_keyword.split(" ")) + r"\b"
        return re.search(pattern, normalized_title) is not None

    @staticmethod
    def _keyword_variants(keyword: str) -> List[str]:
        normalized_keyword = TriageService._normalize_search_text(keyword)
        if not normalized_keyword:
            return []
        variants = [normalized_keyword]

        lowered_keyword = normalize_title(keyword or "")
        if "/" in lowered_keyword:
            slash_parts = [item.strip() for item in lowered_keyword.split("/") if item.strip()]
            if len(slash_parts) == 2:
                left = TriageService._normalize_search_text(slash_parts[0])
                right = TriageService._normalize_search_text(slash_parts[1])
                if left:
                    variants.append(left)
                if left and right and " " in left:
                    prefix = left.rsplit(" ", 1)[0].strip()
                    if prefix:
                        variants.append(f"{prefix} {right}")

        return list(dict.fromkeys(item for item in variants if item))

    def _title_matches_keywords(
        self,
        *,
        title: str,
        keywords: List[str],
        required_keywords: Optional[List[str]] = None,
    ) -> bool:
        normalized_title = self._normalize_search_text(title)
        if not normalized_title:
            return False

        keyword_variants = [
            variant
            for keyword in keywords
            for variant in self._keyword_variants(keyword)
        ]
        if not keyword_variants:
            return True

        has_keyword_match = any(
            self._keyword_matches_title(normalized_title=normalized_title, keyword=keyword)
            for keyword in keyword_variants
        )
        if not has_keyword_match:
            return False

        required_variants = [
            variant
            for keyword in (required_keywords or [])
            for variant in self._keyword_variants(keyword)
        ]
        if not required_variants:
            return True
        return any(
            self._keyword_matches_title(normalized_title=normalized_title, keyword=keyword)
            for keyword in required_variants
        )

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

    def discover_for_profile(
        self,
        *,
        monitor_profile_id: int,
        max_results: int,
        published_after: Optional[datetime] = None,
        published_before: Optional[datetime] = None,
    ):
        logger.info(
            "DISCOVERY START: profile_id=%s max_results=%d mock=%s",
            monitor_profile_id, max_results, self.settings.enable_mock_discovery
        )

        profile = self._require_profile(monitor_profile_id)

        keywords = self._monitoring_keywords(profile)
        required_product_keywords = self.monitor_repository.unpack_key_products(profile)
        languages = self.monitor_repository.unpack_languages(profile)
        markets = self.monitor_repository.unpack_markets(profile)

        logger.info(
            "DISCOVERY PROFILE: name='%s' keywords=%d languages=%d markets=%d",
            profile.name, len(keywords), len(languages), len(markets)
        )
        logger.debug("DISCOVERY KEYWORDS: %s", keywords)
        logger.debug("DISCOVERY LANGUAGES: %s", languages)
        logger.debug("DISCOVERY MARKETS: %s", markets)

        if self.settings.enable_mock_discovery:
            logger.info("DISCOVERY: using mock seed (mock discovery enabled)")
            discovered = self.discovery_service.mock_seed_for_profile(profile=profile, max_results=max_results)
            expanded_keywords = list(dict.fromkeys(keywords))
        else:
            logger.info("DISCOVERY: building query plan with Gemini/keyword fallback")
            plan = self.discovery_keyword_service.build_plan(keywords=keywords, languages=languages, markets=markets)
            expanded_keywords = list(dict.fromkeys([*plan.match_keywords, *keywords]))
            logger.info(
                "DISCOVERY PLAN: query_specs=%d match_keywords=%d",
                len(plan.query_specs), len(plan.match_keywords)
            )
            logger.debug("DISCOVERY QUERY SPECS: %s", plan.query_specs)

            discovered = self.discovery_service.discover_live_with_specs(
                query_specs=plan.query_specs,
                max_results=max_results,
                published_after=published_after,
                published_before=published_before,
            )

        logger.info("DISCOVERY RAW RESULTS: %d videos from search", len(discovered))

        discovered = filter_discovered_videos_by_publish_window(
            discovered,
            published_after=published_after,
            published_before=published_before,
        )
        logger.info("DISCOVERY AFTER WINDOW FILTER: %d videos", len(discovered))

        filtered_discovered = [
            item
            for item in discovered
            if self._title_matches_keywords(
                title=item.title,
                keywords=expanded_keywords,
                required_keywords=required_product_keywords,
            )
        ]
        logger.info(
            "DISCOVERY AFTER TITLE FILTER: %d videos (filtered out %d)",
            len(filtered_discovered), len(discovered) - len(filtered_discovered)
        )

        persisted = []
        for item in filtered_discovered:
            relevance_score, relevance_reason = self.relevance_service.score(
                title=item.title,
                description=item.description,
                keywords=expanded_keywords,
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
                logger.debug("DISCOVERY PERSISTED: video_id=%s title='%s'", candidate.id, item.title[:50])
            else:
                logger.debug("DISCOVERY SKIPPED: video already in other project title='%s'", item.title[:50])

        logger.info(
            "DISCOVERY COMPLETE: profile_id=%s persisted=%d (was filtered: %d -> %d -> %d)",
            monitor_profile_id, len(persisted), len(discovered) + (len(discovered) - len(filtered_discovered)),
            len(discovered), len(filtered_discovered)
        )

        self.audit_repository.record(
            actor="system",
            action="discover_videos",
            resource_type="monitor_profile",
            resource_id=str(monitor_profile_id),
            details=f"discovered_count={len(persisted)}",
        )
        return persisted

    def list_candidates(
        self,
        *,
        monitor_profile_id: int = None,
        owner_user_id: Optional[str] = None,
        queue_state=None,
        risk_level=None,
        sentiment: str = None,
        title_query: str = None,
    ):
        return self.video_repository.list(
            monitor_profile_id=monitor_profile_id,
            queue_state=queue_state,
            risk_level=risk_level,
            sentiment=sentiment,
            title_query=title_query,
            owner_user_id=owner_user_id,
        )

    def search_candidates(self, *, monitor_profile_id: int, query: str, max_results: int) -> List[dict]:
        profile = self._require_profile(monitor_profile_id)

        profile_keywords = self._monitoring_keywords(profile)
        query_keywords = [item.strip() for item in query.split(",") if item.strip()]
        if not query_keywords:
            raise ValueError("At least one keyword is required for search.")

        languages = self.monitor_repository.unpack_languages(profile)
        markets = self.monitor_repository.unpack_markets(profile)
        if self.settings.enable_mock_discovery:
            discovered = self.discovery_service.mock_seed_for_keywords(
                keywords=query_keywords,
                languages=languages,
                markets=markets,
                max_results=max_results,
            )
            scoring_keywords = list(dict.fromkeys([*profile_keywords, *query_keywords]))
        else:
            plan = self.discovery_keyword_service.build_plan(
                keywords=query_keywords,
                languages=languages,
                markets=markets,
            )
            discovered = self.discovery_service.discover_live_with_specs(
                query_specs=plan.query_specs,
                max_results=max_results,
            )
            scoring_keywords = list(dict.fromkeys([*profile_keywords, *query_keywords, *plan.match_keywords]))

        candidates = []
        for item in discovered:
            relevance_score, relevance_reason = self.relevance_service.score(
                title=item.title,
                description=item.description,
                keywords=scoring_keywords,
            )
            existing = self.video_repository.get_by_youtube_id(
                item.youtube_video_id,
                monitor_profile_id=monitor_profile_id,
            )
            if existing is None:
                can_add = True
                block_reason = None
            else:
                can_add = False
                block_reason = "Already in this project"

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
        keywords = self._monitoring_keywords(profile)
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

    def assign_video(self, *, video_id: int, assigned_user_id: Optional[str], actor: str):
        normalized_assignee = (assigned_user_id or "").strip()
        if normalized_assignee:
            app_user = self.app_user_repository.get(normalized_assignee)
            if app_user is None or not app_user.is_active:
                raise ValueError("Assigned user not found.")
        existing = self.video_repository.get_by_id(video_id)
        if existing is None:
            raise ValueError("Video candidate not found.")
        previous_assignee = existing.assigned_user_id or ""
        candidate = self.video_repository.assign_user(
            video_id=video_id,
            assigned_user_id=normalized_assignee or None,
            actor=actor,
        )
        if candidate is None:
            raise ValueError("Video candidate not found.")
        self.audit_repository.record(
            actor=actor,
            action="assign_video",
            resource_type="video_candidate",
            resource_id=str(video_id),
            details=f"from={previous_assignee or 'none'} to={normalized_assignee or 'none'}",
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

        keywords = self._monitoring_keywords(profile)
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
