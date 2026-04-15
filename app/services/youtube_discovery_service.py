from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
from uuid import uuid5, NAMESPACE_DNS

import httpx

from app.config import get_settings
from app.models.monitor_profile import MonitorProfile
from app.repositories.monitor_repository import MonitorRepository
from app.services.discovery_types import DiscoveryQuerySpec
from app.services.types import DiscoveredVideo

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


class YouTubeDiscoveryService:
    """YouTube search with explicit per-market query specs (from Gemini + user keywords)."""

    def __init__(self):
        self.settings = get_settings()

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
            return self.discover_live_with_specs(query_specs=query_specs, max_results=max_results)

        seed_videos = self._seed_videos(keywords=filtered_keywords, languages=languages, markets=markets)
        return seed_videos[:max_results]

    def discover_live_with_specs(self, *, query_specs: List[DiscoveryQuerySpec], max_results: int) -> List[DiscoveredVideo]:
        specs = list(query_specs)
        if not specs:
            specs = [("product", "en", "")]
        if not self.settings.enable_mock_discovery:
            api_key = self.settings.youtube_data_api_key.strip()
            if api_key:
                return self._discover_with_data_api(query_specs=specs, api_key=api_key, max_results=max_results)
            return self._discover_with_yt_dlp(query_specs=specs, max_results=max_results)
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
        q_base = " ".join(base_kw).strip()
        if len(q_base) > 100:
            q_base = q_base[:100].rsplit(" ", 1)[0] or q_base[:100]
        normalized_langs = cls._normalized_languages(languages)
        market_rows = cls._normalized_markets(markets)
        specs: List[DiscoveryQuerySpec] = []
        seen = set()
        for language_code in normalized_langs:
            for region_code, _name in market_rows:
                key = f"{language_code}:{region_code}:{q_base.lower()}"
                if key in seen:
                    continue
                seen.add(key)
                specs.append((q_base, language_code, region_code))
        return specs

    def _discover_with_data_api(
        self, *, query_specs: List[Tuple[str, str, str]], api_key: str, max_results: int
    ) -> List[DiscoveredVideo]:
        discovered_by_id: Dict[str, DiscoveredVideo] = {}
        query_count = max(1, len(query_specs))
        if query_count == 1:
            per_query_limit = max(1, min(50, max_results))
        else:
            per_query_limit = max(2, min(10, (max_results // query_count) + 2))
        timeout_seconds = max(3.0, min(30.0, float(self.settings.youtube_comments_timeout_seconds)))

        for query, language_code, region_code in query_specs:
            params = {
                "part": "snippet",
                "type": "video",
                "q": query,
                "maxResults": per_query_limit,
                "key": api_key,
            }
            if language_code:
                params["relevanceLanguage"] = language_code
            if region_code:
                params["regionCode"] = region_code
            try:
                response = httpx.get(YOUTUBE_SEARCH_ENDPOINT, params=params, timeout=timeout_seconds)
            except (httpx.TimeoutException, httpx.TransportError):
                continue
            if response.status_code >= 400:
                continue
            payload = response.json()
            items = payload.get("items") if isinstance(payload, dict) else []
            if not isinstance(items, list):
                continue
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
        return list(discovered_by_id.values())[:max_results]

    def _discover_with_yt_dlp(
        self, *, query_specs: List[Tuple[str, str, str]], max_results: int
    ) -> List[DiscoveredVideo]:
        try:
            import yt_dlp
        except ImportError:
            return []

        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "ignoreerrors": True,
            "noplaylist": True,
        }
        query_count = max(1, len(query_specs))
        if query_count == 1:
            per_query_limit = max(1, max_results)
        else:
            per_query_limit = max(2, (max_results // query_count) + 2)
        discovered_by_id: Dict[str, DiscoveredVideo] = {}
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                for query, language_code, _region_code in query_specs:
                    try:
                        payload = ydl.extract_info(f"ytsearch{per_query_limit}:{query}", download=False)
                    except Exception:  # noqa: BLE001
                        continue
                    results = payload.get("entries", []) if payload else []
                    for item in results:
                        video_id = item.get("id")
                        title = item.get("title")
                        video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None
                        if not video_id or not title or not video_url or video_id in discovered_by_id:
                            continue

                        channel = item.get("channel") or item.get("uploader") or "Unknown Channel"
                        description = (item.get("description") or title).strip()
                        timestamp = item.get("timestamp")
                        published_at = (
                            datetime.fromtimestamp(timestamp, tz=timezone.utc)
                            if isinstance(timestamp, (int, float))
                            else datetime.now(timezone.utc)
                        )
                        discovered_by_id[video_id] = DiscoveredVideo(
                            youtube_video_id=video_id,
                            video_url=video_url,
                            title=title,
                            channel_name=channel,
                            language=language_code,
                            published_at=published_at,
                            description=description or title,
                        )
        except Exception:  # noqa: BLE001
            return []

        return list(discovered_by_id.values())[:max_results]

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
        return deduped or ["en"]

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
