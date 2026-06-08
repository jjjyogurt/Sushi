import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from uuid import uuid5, NAMESPACE_DNS

import httpx

from app.config import get_settings
from app.models.monitor_profile import MonitorProfile
from app.repositories.monitor_repository import MonitorRepository
from app.services.discovery_types import DiscoveryQuerySpec
from app.services.serpapi_youtube_discovery_service import (
    SerpApiVideoHit,
    SerpApiYouTubeDiscoveryService,
)
from app.services.types import DiscoveredVideo

logger = logging.getLogger(__name__)

MAX_DISCOVERY_LANGUAGES = 3

LANGUAGE_NORMALIZATION_MAP: Dict[str, str] = {
    "en": "en",
    "english": "en",
    "fr": "fr",
    "french": "fr",
    "francais": "fr",
    "français": "fr",
    "de": "de",
    "german": "de",
    "es": "es",
    "spanish": "es",
    "es-419": "es",
    "it": "it",
    "italian": "it",
    "nl": "nl",
    "dutch": "nl",
    "pl": "pl",
    "polish": "pl",
    "pt": "pt",
    "portuguese": "pt",
    "pt-br": "pt-br",
    "pt-pt": "pt",
    "ja": "ja",
    "japanese": "ja",
    "ko": "ko",
    "korean": "ko",
    "zh-hans": "zh-hans",
    "zh-hant": "zh-hant",
    "zh": "zh-hans",
    "hi": "hi",
    "hindi": "hi",
    "id": "id",
    "indonesian": "id",
    "th": "th",
    "thai": "th",
    "vi": "vi",
    "vietnamese": "vi",
    "ar": "ar",
    "arabic": "ar",
    "tr": "tr",
    "turkish": "tr",
}

MARKET_REGION_MAP: Dict[str, str] = {
    "us": "US",
    "usa": "US",
    "united states": "US",
    "ca": "CA",
    "canada": "CA",
    "gb": "GB",
    "uk": "GB",
    "united kingdom": "GB",
    "de": "DE",
    "germany": "DE",
    "fr": "FR",
    "france": "FR",
    "es": "ES",
    "spain": "ES",
    "it": "IT",
    "italy": "IT",
    "nl": "NL",
    "netherlands": "NL",
    "se": "SE",
    "sweden": "SE",
    "pl": "PL",
    "poland": "PL",
    "jp": "JP",
    "japan": "JP",
    "kr": "KR",
    "korea": "KR",
    "south korea": "KR",
    "tw": "TW",
    "taiwan": "TW",
    "hk": "HK",
    "hong kong": "HK",
    "sg": "SG",
    "singapore": "SG",
    "in": "IN",
    "india": "IN",
    "au": "AU",
    "australia": "AU",
    "br": "BR",
    "brazil": "BR",
    "mx": "MX",
    "mexico": "MX",
    "ae": "AE",
    "uae": "AE",
    "united arab emirates": "AE",
}

MARKET_NAME_BY_REGION: Dict[str, str] = {
    "US": "United States",
    "CA": "Canada",
    "GB": "United Kingdom",
    "DE": "Germany",
    "FR": "France",
    "ES": "Spain",
    "IT": "Italy",
    "NL": "Netherlands",
    "SE": "Sweden",
    "PL": "Poland",
    "JP": "Japan",
    "KR": "South Korea",
    "TW": "Taiwan",
    "HK": "Hong Kong",
    "SG": "Singapore",
    "IN": "India",
    "AU": "Australia",
    "BR": "Brazil",
    "MX": "Mexico",
    "AE": "United Arab Emirates",
}

YOUTUBE_SEARCH_ENDPOINT = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"


def _coerce_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _format_youtube_search_datetime(value: datetime) -> str:
    return _coerce_utc(value).isoformat().replace("+00:00", "Z")


def filter_discovered_videos_by_publish_window(
    videos: List[DiscoveredVideo],
    *,
    published_after: Optional[datetime] = None,
    published_before: Optional[datetime] = None,
) -> List[DiscoveredVideo]:
    """Keep videos in the half-open window [published_after, published_before) in UTC."""
    if published_after is None and published_before is None:
        return list(videos)
    after_ts = _coerce_utc(published_after) if published_after is not None else None
    before_ts = _coerce_utc(published_before) if published_before is not None else None
    result: List[DiscoveredVideo] = []
    for item in videos:
        ts = _coerce_utc(item.published_at)
        if after_ts is not None and ts < after_ts:
            continue
        if before_ts is not None and ts >= before_ts:
            continue
        result.append(item)
    return result


class YouTubeDiscoveryService:
    """YouTube search with explicit per-market query specs (from Gemini + user keywords)."""

    def __init__(self):
        self.settings = get_settings()
        self.serpapi_discovery_service = SerpApiYouTubeDiscoveryService(self.settings)
        self.last_discovery_stats: Dict[str, int | str] = {}

    def discover(self, *, profile: MonitorProfile, max_results: int) -> List[DiscoveredVideo]:
        """Legacy entry: builds fallback specs only (no Gemini). Prefer discover_live_with_specs from TriageService."""
        keywords = list(
            dict.fromkeys([*MonitorRepository.unpack_keywords(profile), *MonitorRepository.unpack_key_products(profile)])
        )
        languages = MonitorRepository.unpack_languages(profile)
        markets = MonitorRepository.unpack_markets(profile)
        return self.discover_by_keywords(
            keywords=keywords,
            languages=languages,
            markets=markets,
            max_results=max_results,
        )

    def discover_by_keywords(
        self, *, keywords: List[str], languages: List[str], markets: List[str], max_results: int
    ) -> List[DiscoveredVideo]:
        filtered_keywords = [item.strip() for item in keywords if item and item.strip()]
        if not self.settings.enable_mock_discovery:
            query_specs = self._fallback_query_specs(keywords=filtered_keywords, languages=languages, markets=markets)
            if not query_specs:
                query_specs = [("product", "en", "")]
            return self.discover_live_with_specs(
                query_specs=query_specs,
                max_results=max_results,
            )

        seed_videos = self._seed_videos(keywords=filtered_keywords, languages=languages, markets=markets)
        return seed_videos[:max_results]

    def discover_live_with_specs(
        self,
        *,
        query_specs: List[DiscoveryQuerySpec],
        max_results: int,
        published_after: Optional[datetime] = None,
        published_before: Optional[datetime] = None,
        include_serpapi: bool = True,
    ) -> List[DiscoveredVideo]:
        specs = list(query_specs)
        if not specs:
            specs = [("product", "en", "")]
            logger.warning("Discover live: no specs provided, using default")
        self.last_discovery_stats = {}

        logger.info(
            "Discover live START: specs=%d mock=%s api_key_set=%s",
            len(specs),
            self.settings.enable_mock_discovery,
            bool(self.settings.youtube_data_api_key.strip())
        )

        if not self.settings.enable_mock_discovery:
            api_key = self.settings.youtube_data_api_key.strip()
            if api_key:
                source_policy = "serpapi_primary_data_api_supplement" if (
                    include_serpapi and self.settings.serpapi_api_key.strip()
                ) else "youtube_data_api_only"
                self.last_discovery_stats["manual_discovery_source_policy"] = source_policy
                logger.info("Discover live: source_policy=%s", source_policy)

                serpapi_results = []
                if include_serpapi and self.settings.serpapi_api_key.strip():
                    serpapi_results = self._discover_with_serpapi(
                        query_specs=specs,
                        api_key=api_key,
                        max_results=max_results,
                        published_after=published_after,
                        published_before=published_before,
                    )
                data_api_results = self._discover_with_data_api(
                    query_specs=specs,
                    api_key=api_key,
                    max_results=max_results,
                    published_after=published_after,
                    published_before=published_before,
                )
                merged = self._merge_discovered_results(
                    primary=serpapi_results,
                    fallback=data_api_results,
                    max_results=max_results,
                )
                logger.info(
                    "Discover live COMPLETE: serpapi=%d data_api=%d merged=%d",
                    len(serpapi_results), len(data_api_results), len(merged)
                )
                self.last_discovery_stats["merged_count"] = len(merged)
                return merged
            logger.info("Discover live: no API key, using yt-dlp fallback")
            self.last_discovery_stats["manual_discovery_source_policy"] = "yt_dlp_fallback"
            return self._discover_with_yt_dlp(
                query_specs=specs,
                max_results=max_results,
                published_after=published_after,
                published_before=published_before,
            )
        logger.info("Discover live: mock discovery enabled, returning empty")
        self.last_discovery_stats["manual_discovery_source_policy"] = "mock"
        return []

    def mock_seed_for_profile(self, *, profile: MonitorProfile, max_results: int) -> List[DiscoveredVideo]:
        keywords = list(
            dict.fromkeys([*MonitorRepository.unpack_keywords(profile), *MonitorRepository.unpack_key_products(profile)])
        )
        languages = MonitorRepository.unpack_languages(profile)
        markets = MonitorRepository.unpack_markets(profile)
        return self._seed_videos(keywords=keywords, languages=languages, markets=markets)[:max_results]

    def mock_seed_for_keywords(
        self, *, keywords: List[str], languages: List[str], markets: List[str], max_results: int
    ) -> List[DiscoveredVideo]:
        filtered = [item.strip() for item in keywords if item and item.strip()]
        return self._seed_videos(keywords=filtered, languages=languages, markets=markets)[:max_results]

    @classmethod
    def _fallback_query_specs(cls, *, keywords: List[str], languages: List[str], markets: List[str]) -> List[DiscoveryQuerySpec]:
        base_kw = [item.strip() for item in keywords if item and item.strip()]
        if not base_kw:
            return []
        query_seeds: List[str] = []
        for keyword in base_kw:
            query = keyword
            if len(query) > 100:
                query = query[:100].rsplit(" ", 1)[0] or query[:100]
            if query and query not in query_seeds:
                query_seeds.append(query)
        normalized_langs = cls._normalized_languages(languages)
        market_rows = cls._normalized_markets(markets)
        specs: List[DiscoveryQuerySpec] = []
        seen = set()
        for language_code in normalized_langs:
            for region_code, _name in market_rows:
                for query in query_seeds:
                    key = f"{language_code}:{region_code}:{query.lower()}"
                    if key in seen:
                        continue
                    seen.add(key)
                    specs.append((query, language_code, region_code))
        return specs

    def _discover_with_data_api(
        self,
        *,
        query_specs: List[Tuple[str, str, str]],
        api_key: str,
        max_results: int,
        published_after: Optional[datetime] = None,
        published_before: Optional[datetime] = None,
    ) -> List[DiscoveredVideo]:
        discovered_by_id: Dict[str, DiscoveredVideo] = {}
        raw_count = 0
        error_count = 0
        per_query_limit = max(1, min(50, max_results))
        timeout_seconds = max(3.0, min(30.0, float(self.settings.youtube_comments_timeout_seconds)))

        logger.info(
            "YouTube discovery START: queries=%d max_results=%d timeout=%.1fs",
            len(query_specs), max_results, timeout_seconds
        )

        for query, language_code, region_code in query_specs:
            params = {
                "part": "snippet",
                "type": "video",
                "order": "date",
                "q": query,
                "maxResults": per_query_limit,
                "key": api_key,
            }
            if language_code:
                params["relevanceLanguage"] = language_code
            if region_code:
                params["regionCode"] = region_code
            if published_after is not None:
                params["publishedAfter"] = _format_youtube_search_datetime(published_after)
            if published_before is not None:
                params["publishedBefore"] = _format_youtube_search_datetime(published_before)

            logger.debug(
                "YouTube API request: query='%s' lang=%s region=%s",
                query[:50], language_code, region_code
            )

            try:
                response = httpx.get(YOUTUBE_SEARCH_ENDPOINT, params=params, timeout=timeout_seconds)
            except httpx.TimeoutException as e:
                error_count += 1
                logger.error(
                    "YouTube API TIMEOUT: query='%s' lang=%s region=%s timeout=%.1fs error=%s",
                    query[:50], language_code, region_code, timeout_seconds, str(e)
                )
                continue
            except httpx.TransportError as e:
                error_count += 1
                logger.error(
                    "YouTube API TRANSPORT ERROR: query='%s' lang=%s region=%s error=%s type=%s",
                    query[:50], language_code, region_code, str(e), type(e).__name__
                )
                continue
            except Exception as e:
                error_count += 1
                logger.exception(
                    "YouTube API UNEXPECTED ERROR: query='%s' lang=%s region=%s",
                    query[:50], language_code, region_code
                )
                continue

            if response.status_code >= 400:
                error_count += 1
                logger.warning(
                    "YouTube API ERROR RESPONSE: status=%s query='%s' lang=%s region=%s body=%.200s",
                    response.status_code, query[:50], language_code, region_code, response.text
                )
                continue

            try:
                payload = response.json()
            except Exception as e:
                error_count += 1
                logger.error(
                    "YouTube API JSON PARSE ERROR: query='%s' status=%s error=%s body=%.200s",
                    query[:50], response.status_code, str(e), response.text
                )
                continue

            items = payload.get("items") if isinstance(payload, dict) else []
            if not isinstance(items, list):
                error_count += 1
                logger.warning(
                    "YouTube API INVALID ITEMS: query='%s' items_type=%s",
                    query[:50], type(items).__name__
                )
                continue

            logger.info(
                "YouTube API SUCCESS: query='%s' lang=%s region=%s items=%d",
                query[:50], language_code, region_code, len(items)
            )

            valid_count = 0
            raw_count += len(items)
            for item in items:
                if not isinstance(item, dict):
                    continue
                identifier = item.get("id")
                snippet = item.get("snippet")
                if not isinstance(identifier, dict) or not isinstance(snippet, dict):
                    continue
                video_id = str(identifier.get("videoId") or "").strip()
                title = str(snippet.get("title") or "").strip()
                if not video_id or not title or video_id in discovered_by_id:
                    continue
                published_at = self._parse_iso8601_datetime(snippet.get("publishedAt")) or datetime.now(timezone.utc)
                discovered_by_id[video_id] = DiscoveredVideo(
                    youtube_video_id=video_id,
                    video_url=f"https://www.youtube.com/watch?v={video_id}",
                    title=title,
                    channel_name=str(snippet.get("channelTitle") or "Unknown Channel").strip() or "Unknown Channel",
                    language=language_code or "en",
                    published_at=published_at,
                    description=str(snippet.get("description") or title).strip() or title,
                )
                valid_count += 1

            logger.debug(
                "YouTube API valid videos from query: query='%s' valid=%d total_unique=%d",
                query[:50], valid_count, len(discovered_by_id)
            )

        trimmed = filter_discovered_videos_by_publish_window(
            list(discovered_by_id.values()),
            published_after=published_after,
            published_before=published_before,
        )

        logger.info(
            "YouTube discovery COMPLETE: raw=%d after_window=%d max_results=%d",
            len(discovered_by_id), len(trimmed), max_results
        )
        self.last_discovery_stats["data_api_query_count"] = len(query_specs)
        self.last_discovery_stats["data_api_raw_count"] = raw_count
        self.last_discovery_stats["data_api_unique_count"] = len(discovered_by_id)
        self.last_discovery_stats["data_api_error_count"] = error_count

        return trimmed[:max_results]

    def _discover_with_serpapi(
        self,
        *,
        query_specs: List[Tuple[str, str, str]],
        api_key: str,
        max_results: int,
        published_after: Optional[datetime] = None,
        published_before: Optional[datetime] = None,
    ) -> List[DiscoveredVideo]:
        serpapi_result = self.serpapi_discovery_service.discover_video_ids(
            query_specs=query_specs,
            max_results=max_results,
        )
        self.last_discovery_stats["serpapi_query_count"] = serpapi_result.stats.query_count
        self.last_discovery_stats["serpapi_raw_count"] = serpapi_result.stats.raw_count
        self.last_discovery_stats["serpapi_video_id_count"] = serpapi_result.stats.video_id_count
        self.last_discovery_stats["serpapi_error_count"] = serpapi_result.stats.error_count
        enriched = self._fetch_videos_by_ids(
            hits=serpapi_result.hits,
            api_key=api_key,
        )
        trimmed = filter_discovered_videos_by_publish_window(
            enriched,
            published_after=published_after,
            published_before=published_before,
        )
        self.last_discovery_stats["serpapi_enriched_count"] = len(enriched)
        self.last_discovery_stats["serpapi_window_filtered_count"] = len(enriched) - len(trimmed)
        return trimmed[:max_results]

    def _fetch_videos_by_ids(
        self,
        *,
        hits: List[SerpApiVideoHit],
        api_key: str,
    ) -> List[DiscoveredVideo]:
        ordered_hits = []
        seen = set()
        for hit in hits:
            if not hit.video_id or hit.video_id in seen:
                continue
            seen.add(hit.video_id)
            ordered_hits.append(hit)
        if not ordered_hits:
            return []

        hit_by_id = {hit.video_id: hit for hit in ordered_hits}
        timeout_seconds = max(3.0, min(30.0, float(self.settings.youtube_comments_timeout_seconds)))
        videos_by_id: Dict[str, DiscoveredVideo] = {}

        for start in range(0, len(ordered_hits), 50):
            batch = ordered_hits[start : start + 50]
            params = {
                "part": "snippet",
                "id": ",".join(hit.video_id for hit in batch),
                "key": api_key,
            }
            try:
                response = httpx.get(YOUTUBE_VIDEOS_ENDPOINT, params=params, timeout=timeout_seconds)
            except httpx.TimeoutException as error:
                logger.warning("YouTube videos.list timeout while enriching SerpAPI IDs: error=%s", error)
                continue
            except httpx.TransportError as error:
                logger.warning("YouTube videos.list transport error while enriching SerpAPI IDs: error=%s", error)
                continue

            if response.status_code >= 400:
                logger.warning(
                    "YouTube videos.list error while enriching SerpAPI IDs: status=%s body=%.200s",
                    response.status_code,
                    response.text,
                )
                continue

            try:
                payload = response.json()
            except ValueError as error:
                logger.warning(
                    "YouTube videos.list JSON parse error while enriching SerpAPI IDs: error=%s body=%.200s",
                    error,
                    response.text,
                )
                continue

            items = payload.get("items") if isinstance(payload, dict) else []
            if not isinstance(items, list):
                logger.warning("YouTube videos.list invalid items while enriching SerpAPI IDs")
                continue

            for item in items:
                if not isinstance(item, dict):
                    continue
                video_id = str(item.get("id") or "").strip()
                snippet = item.get("snippet")
                if not video_id or not isinstance(snippet, dict):
                    continue
                title = str(snippet.get("title") or "").strip()
                if not title:
                    continue
                hit = hit_by_id.get(video_id)
                language_code = hit.language_code if hit else "en"
                published_at = self._parse_iso8601_datetime(snippet.get("publishedAt")) or datetime.now(timezone.utc)
                videos_by_id[video_id] = DiscoveredVideo(
                    youtube_video_id=video_id,
                    video_url=f"https://www.youtube.com/watch?v={video_id}",
                    title=title,
                    channel_name=str(snippet.get("channelTitle") or "Unknown Channel").strip() or "Unknown Channel",
                    language=language_code or "en",
                    published_at=published_at,
                    description=str(snippet.get("description") or title).strip() or title,
                )

        return [videos_by_id[hit.video_id] for hit in ordered_hits if hit.video_id in videos_by_id]

    def _discover_with_yt_dlp(
        self,
        *,
        query_specs: List[Tuple[str, str, str]],
        max_results: int,
        published_after: Optional[datetime] = None,
        published_before: Optional[datetime] = None,
    ) -> List[DiscoveredVideo]:
        try:
            import yt_dlp
        except ImportError as e:
            logger.error("yt-dlp import failed: %s", e)
            return []

        logger.info("yt-dlp discovery START: queries=%d max_results=%d", len(query_specs), max_results)

        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "ignoreerrors": True,
            "noplaylist": True,
        }
        per_query_limit = max(1, max_results)
        discovered_by_id: Dict[str, DiscoveredVideo] = {}

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                for query, language_code, _region_code in query_specs:
                    logger.debug("yt-dlp query: '%s' limit=%d", query[:50], per_query_limit)
                    try:
                        payload = ydl.extract_info(f"ytsearch{per_query_limit}:{query}", download=False)
                    except Exception as e:  # noqa: BLE001
                        logger.warning("yt-dlp query failed: query='%s' error=%s", query[:50], e)
                        continue

                    results = payload.get("entries", []) if payload else []
                    logger.debug("yt-dlp results: query='%s' entries=%d", query[:50], len(results))

                    for item in results:
                        if not isinstance(item, dict):
                            continue
                        video = self._discovered_video_from_yt_dlp_item(
                            item=item,
                            language_code=language_code,
                        )
                        if video is None or video.youtube_video_id in discovered_by_id:
                            continue
                        discovered_by_id[video.youtube_video_id] = video
        except Exception as e:  # noqa: BLE001
            logger.exception("yt-dlp discovery failed: %s", e)
            return []

        trimmed = filter_discovered_videos_by_publish_window(
            list(discovered_by_id.values()),
            published_after=published_after,
            published_before=published_before,
        )

        logger.info(
            "yt-dlp discovery COMPLETE: raw=%d after_window=%d final=%d",
            len(discovered_by_id), len(trimmed), min(len(trimmed), max_results)
        )
        return trimmed[:max_results]

    @staticmethod
    def _merge_discovered_results(
        *,
        primary: List[DiscoveredVideo],
        fallback: List[DiscoveredVideo],
        max_results: int,
    ) -> List[DiscoveredVideo]:
        merged_by_id: Dict[str, DiscoveredVideo] = {}
        for item in [*primary, *fallback]:
            if item.youtube_video_id in merged_by_id:
                continue
            merged_by_id[item.youtube_video_id] = item
            if len(merged_by_id) >= max_results:
                break
        return list(merged_by_id.values())

    @classmethod
    def _discovered_video_from_yt_dlp_item(cls, *, item: dict, language_code: str) -> Optional[DiscoveredVideo]:
        video_id = str(item.get("id") or "").strip()
        title = str(item.get("title") or "").strip()
        video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else ""
        if not video_id or not title or not video_url:
            return None

        channel = str(item.get("channel") or item.get("uploader") or "Unknown Channel").strip()
        description = str(item.get("description") or title).strip()
        return DiscoveredVideo(
            youtube_video_id=video_id,
            video_url=video_url,
            title=title,
            channel_name=channel or "Unknown Channel",
            language=language_code,
            published_at=cls._parse_yt_dlp_published_at(item),
            description=description or title,
        )

    @staticmethod
    def _parse_yt_dlp_published_at(item: dict) -> datetime:
        timestamp = item.get("timestamp")
        if isinstance(timestamp, (int, float)):
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)

        upload_date = str(item.get("upload_date") or "").strip()
        if len(upload_date) == 8 and upload_date.isdigit():
            try:
                return datetime(
                    int(upload_date[0:4]),
                    int(upload_date[4:6]),
                    int(upload_date[6:8]),
                    tzinfo=timezone.utc,
                )
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_iso8601_datetime(raw_value: object):
        if raw_value is None:
            return None
        raw_text = str(raw_value).strip()
        if not raw_text:
            return None
        try:
            return datetime.fromisoformat(raw_text.replace("Z", "+00:00"))
        except ValueError:
            return None

    @staticmethod
    def _normalize_language_code(language: str) -> str:
        raw_value = str(language or "").strip().lower()
        if not raw_value:
            return "en"
        if raw_value in LANGUAGE_NORMALIZATION_MAP:
            return LANGUAGE_NORMALIZATION_MAP[raw_value]
        if raw_value.startswith("es-"):
            return "es"
        if raw_value.startswith("pt-"):
            return "pt-br" if "br" in raw_value else "pt"
        return raw_value

    @classmethod
    def _normalized_languages(cls, languages: List[str]) -> List[str]:
        normalized = [cls._normalize_language_code(language) for language in languages if str(language or "").strip()]
        deduped: List[str] = []
        for language in normalized:
            if language not in deduped:
                deduped.append(language)
        if not deduped:
            return ["en"]
        if "en" not in deduped:
            return deduped[:MAX_DISCOVERY_LANGUAGES]
        prioritized = [language for language in deduped if language != "en"]
        prioritized = prioritized[: MAX_DISCOVERY_LANGUAGES - 1]
        prioritized.append("en")
        return prioritized

    @staticmethod
    def _normalize_market_region(market: str) -> str:
        raw_value = str(market or "").strip()
        if not raw_value:
            return ""
        lowered = raw_value.lower()
        if lowered == "global":
            return ""
        mapped = MARKET_REGION_MAP.get(lowered)
        if mapped:
            return mapped
        if len(raw_value) == 2 and raw_value.isalpha():
            return raw_value.upper()
        return ""

    @classmethod
    def _normalized_markets(cls, markets: List[str]) -> List[Tuple[str, str]]:
        normalized: List[Tuple[str, str]] = []
        seen = set()
        for market in markets:
            raw_market = str(market or "").strip()
            if not raw_market:
                continue
            region_code = cls._normalize_market_region(raw_market)
            market_name = MARKET_NAME_BY_REGION.get(region_code, raw_market)
            marker = (region_code, market_name.lower())
            if marker not in seen:
                seen.add(marker)
                normalized.append((region_code, market_name))
        return normalized or [("", "")]

    def _seed_videos(self, *, keywords: List[str], languages: List[str], markets: List[str]) -> List[DiscoveredVideo]:
        default_keyword = keywords[0] if keywords else "product"
        default_language = languages[0] if languages else "en"
        default_market = markets[0] if markets else "global"

        now = datetime.now(timezone.utc)
        drafts = [
            (
                f"{default_keyword} hands-on review in {default_market}",
                default_language,
                "Detailed product test with setup walkthrough and user concerns.",
                "CreatorLab",
                now - timedelta(hours=2),
            ),
            (
                f"My honest thoughts about {default_keyword} after 7 days",
                default_language,
                "Experience-focused review including battery, controls, and reliability.",
                "TechFocus",
                now - timedelta(hours=5),
            ),
            (
                f"Top mistakes people make with {default_keyword}",
                default_language,
                "Common onboarding and feature usage pain points from user comments.",
                "ReviewStation",
                now - timedelta(hours=8),
            ),
        ]

        videos: List[DiscoveredVideo] = []
        for title, language, description, channel_name, published_at in drafts:
            seed = f"{channel_name}:{title}:{published_at.isoformat()}"
            video_id = uuid5(NAMESPACE_DNS, seed).hex[:12]
            videos.append(
                DiscoveredVideo(
                    youtube_video_id=video_id,
                    video_url=f"https://www.youtube.com/watch?v={video_id}",
                    title=title,
                    channel_name=channel_name,
                    language=language,
                    published_at=published_at,
                    description=description,
                )
            )
        return videos
