import logging
import re
from typing import Dict, List, Optional
from datetime import datetime, timedelta, timezone

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
from app.services.youtube_video_stats_service import YouTubeVideoStatsService
from app.utils.text import normalize_title
from app.utils.youtube import extract_video_id, fetch_oembed_metadata

logger = logging.getLogger(__name__)

VIEW_COUNT_STALE_AFTER = timedelta(hours=24)
CJK_LANGUAGE_CODES = {"ja", "ko", "zh", "zh-hans", "zh-hant"}
CJK_TEXT_PATTERN = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff\uac00-\ud7af]")


class TriageService:
    def __init__(self, session: Session):
        self.analysis_repository = AnalysisRepository(session)
        self.app_user_repository = AppUserRepository(session)
        self.audit_repository = AuditRepository(session)
        self.monitor_repository = MonitorRepository(session)
        self.video_repository = VideoRepository(session)
        self.relevance_service = RelevanceService()
        self.discovery_service = YouTubeDiscoveryService()
        self.youtube_video_stats_service = YouTubeVideoStatsService()
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

    def _keyword_matches_text(self, *, normalized_text: str, keyword: str) -> bool:
        normalized_keyword = self._normalize_search_text(keyword)
        if not normalized_keyword:
            return False
        if self._contains_non_ascii(normalized_keyword):
            return normalized_keyword in normalized_text
        pattern = r"\b" + r"\s+".join(re.escape(token) for token in normalized_keyword.split(" ")) + r"\b"
        return re.search(pattern, normalized_text) is not None

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

    def _text_matches_keywords(
        self,
        *,
        text: str,
        keywords: List[str],
    ) -> bool:
        normalized_text = self._normalize_search_text(text)
        if not normalized_text:
            return False

        keyword_variants = [
            variant
            for keyword in keywords
            for variant in self._keyword_variants(keyword)
        ]
        if not keyword_variants:
            return True

        return any(
            self._keyword_matches_text(normalized_text=normalized_text, keyword=keyword)
            for keyword in keyword_variants
        )

    def _candidate_matches_keywords(self, *, item: DiscoveredVideo, keywords: List[str]) -> bool:
        return self._text_matches_keywords(
            text=item.title,
            keywords=keywords,
        ) or self._text_matches_keywords(
            text=item.description,
            keywords=keywords,
        )

    @staticmethod
    def _allows_cjk_language(languages: List[str]) -> bool:
        normalized_languages = {
            YouTubeDiscoveryService._normalize_language_code(str(language or ""))
            for language in languages
            if str(language or "").strip()
        }
        return any(language in CJK_LANGUAGE_CODES for language in normalized_languages)

    def _candidate_matches_language_guard(self, *, item: DiscoveredVideo, languages: List[str]) -> bool:
        if self._allows_cjk_language(languages):
            return True
        searchable_text = f"{item.title or ''} {item.channel_name or ''}".strip()
        return CJK_TEXT_PATTERN.search(searchable_text) is None

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
        time_trigger: Optional[str] = None,
    ):
        normalized_time_trigger = str(time_trigger or "manual_unspecified").strip() or "manual_unspecified"
        logger.info(
            "DISCOVERY START: profile_id=%s max_results=%d mock=%s time_trigger=%s",
            monitor_profile_id, max_results, self.settings.enable_mock_discovery, normalized_time_trigger
        )

        profile = self._require_profile(monitor_profile_id)

        keywords = self._monitoring_keywords(profile)
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
            query_count = len(plan.query_specs)
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
        if self.settings.enable_mock_discovery:
            query_count = 0

        logger.info("DISCOVERY RAW RESULTS: %d videos from search", len(discovered))
        raw_count = len(discovered)

        discovered = filter_discovered_videos_by_publish_window(
            discovered,
            published_after=published_after,
            published_before=published_before,
        )
        logger.info("DISCOVERY AFTER WINDOW FILTER: %d videos", len(discovered))
        window_filtered_count = raw_count - len(discovered)

        filtered_discovered = [
            item
            for item in discovered
            if self._candidate_matches_keywords(
                item=item,
                keywords=expanded_keywords,
            )
            and self._candidate_matches_language_guard(
                item=item,
                languages=languages,
            )
        ]
        relevance_filtered_count = len(discovered) - len(filtered_discovered)
        logger.info(
            "DISCOVERY AFTER RELEVANCE FILTER: %d videos (filtered out %d)",
            len(filtered_discovered), relevance_filtered_count
        )

        persisted = []
        duplicate_or_updated_count = 0
        for item in filtered_discovered:
            relevance_score, relevance_reason = self.relevance_service.score(
                title=item.title,
                description=item.description,
                keywords=expanded_keywords,
            )
            existing = self.video_repository.get_by_youtube_id(
                item.youtube_video_id,
                monitor_profile_id=monitor_profile_id,
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
                if existing is not None:
                    duplicate_or_updated_count += 1
                logger.debug("DISCOVERY PERSISTED: video_id=%s title='%s'", candidate.id, item.title[:50])
            else:
                logger.debug("DISCOVERY SKIPPED: video already in other project title='%s'", item.title[:50])

        logger.info(
            "DISCOVERY COMPLETE: profile_id=%s persisted=%d (was filtered: %d -> %d -> %d)",
            monitor_profile_id, len(persisted), len(discovered) + relevance_filtered_count,
            len(discovered), len(filtered_discovered)
        )

        discovery_stats = self.discovery_service.last_discovery_stats
        stats_details = " ".join(
            f"{key}={value}"
            for key, value in sorted(discovery_stats.items())
        )
        audit_details = (
            f"time_trigger={normalized_time_trigger} "
            f"published_after={published_after.isoformat() if published_after else 'none'} "
            f"published_before={published_before.isoformat() if published_before else 'none'} "
            f"query_count={query_count} "
            f"raw_count={raw_count} "
            f"window_filtered_count={window_filtered_count} "
            f"relevance_filtered_count={relevance_filtered_count} "
            f"saved_count={len(persisted)} "
            f"duplicate_or_updated_count={duplicate_or_updated_count} "
            f"{stats_details} "
            "error_count=0"
        )
        self.audit_repository.record(
            actor="system",
            action="discover_videos",
            resource_type="monitor_profile",
            resource_id=str(monitor_profile_id),
            details=audit_details,
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
        sort_by: str = None,
        sort_order: str = None,
    ):
        videos = self.video_repository.list(
            monitor_profile_id=monitor_profile_id,
            queue_state=queue_state,
            risk_level=risk_level,
            sentiment=sentiment,
            title_query=title_query,
            owner_user_id=owner_user_id,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        if str(sort_by or "").strip().lower() == "views":
            self.refresh_stale_view_counts(videos)
            videos = self.video_repository.list(
                monitor_profile_id=monitor_profile_id,
                queue_state=queue_state,
                risk_level=risk_level,
                sentiment=sentiment,
                title_query=title_query,
                owner_user_id=owner_user_id,
                sort_by=sort_by,
                sort_order=sort_order,
            )
        return videos

    def refresh_stale_view_counts(self, videos) -> int:
        now = datetime.now(timezone.utc)
        stale_before = now - VIEW_COUNT_STALE_AFTER
        stale_youtube_ids = []
        for video in videos:
            fetched_at = video.view_count_fetched_at
            if fetched_at is not None and fetched_at.tzinfo is None:
                fetched_at = fetched_at.replace(tzinfo=timezone.utc)
            if video.view_count is not None and fetched_at is not None and fetched_at >= stale_before:
                continue
            stale_youtube_ids = [*stale_youtube_ids, video.youtube_video_id]

        unique_youtube_ids = list(dict.fromkeys(stale_youtube_ids))
        if not unique_youtube_ids:
            return 0

        try:
            view_counts = self.youtube_video_stats_service.fetch_view_counts(youtube_video_ids=unique_youtube_ids)
        except Exception as error:  # noqa: BLE001
            logger.warning("video list view count refresh failed; continuing with cached values. error=%s", error)
            return 0

        return self.video_repository.update_view_counts(
            view_counts_by_youtube_id=view_counts,
            fetched_at=now,
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

    def delete_videos(self, *, video_ids: List[int], actor: str) -> List[int]:
        normalized_ids = [int(video_id) for video_id in dict.fromkeys(video_ids)]
        if not normalized_ids:
            raise ValueError("At least one video id is required.")

        owned_videos = self.video_repository.list_by_ids_for_user(
            video_ids=normalized_ids,
            owner_user_id=actor,
        )
        owned_ids = {video.id for video in owned_videos}
        missing_ids = [video_id for video_id in normalized_ids if video_id not in owned_ids]
        if missing_ids:
            raise ValueError("One or more selected videos were not found.")

        active_batch_video_ids = self.video_repository.get_active_batch_video_ids(normalized_ids)
        if active_batch_video_ids:
            raise ValueError("One or more selected videos are in an active analysis batch.")

        deleted_count = self.video_repository.delete_many(normalized_ids)
        if deleted_count != len(normalized_ids):
            raise ValueError("One or more selected videos could not be deleted.")

        self.audit_repository.record(
            actor=actor,
            action="bulk_delete_videos",
            resource_type="video_candidate",
            resource_id=",".join(str(video_id) for video_id in normalized_ids),
            details=f"deleted_count={deleted_count}",
        )
        return normalized_ids

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
