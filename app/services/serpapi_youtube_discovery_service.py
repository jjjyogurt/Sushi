import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

import httpx

from app.config import Settings
from app.services.discovery_types import DiscoveryQuerySpec

logger = logging.getLogger(__name__)

SERPAPI_YOUTUBE_ENDPOINT = "https://serpapi.com/search.json"
SERPAPI_YOUTUBE_UPLOAD_DATE_SP = "CAI="

SERPAPI_GL_REGION_OVERRIDES: Dict[str, str] = {
    "GB": "uk",
}


@dataclass(frozen=True)
class SerpApiVideoHit:
    video_id: str
    language_code: str
    region_code: str
    query: str


@dataclass(frozen=True)
class SerpApiDiscoveryStats:
    query_count: int
    raw_count: int
    video_id_count: int
    error_count: int


@dataclass(frozen=True)
class SerpApiDiscoveryResult:
    hits: List[SerpApiVideoHit]
    stats: SerpApiDiscoveryStats


class SerpApiYouTubeDiscoveryService:
    """Market-localized YouTube SERP discovery.

    SerpAPI is only a candidate source here. The caller must validate returned
    video IDs through YouTube Data API before applying publish-window logic or
    saving candidates.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def discover_video_ids(
        self,
        *,
        query_specs: List[DiscoveryQuerySpec],
        max_results: int,
    ) -> SerpApiDiscoveryResult:
        api_key = self.settings.serpapi_api_key.strip()
        if not api_key:
            return SerpApiDiscoveryResult(
                hits=[],
                stats=SerpApiDiscoveryStats(
                    query_count=0,
                    raw_count=0,
                    video_id_count=0,
                    error_count=0,
                ),
            )

        timeout_seconds = max(3.0, min(30.0, float(self.settings.serpapi_timeout_seconds)))
        per_query_limit = max(1, max_results)
        seen: Set[str] = set()
        hits: List[SerpApiVideoHit] = []
        raw_count = 0
        error_count = 0

        logger.info(
            "SerpAPI YouTube discovery START: queries=%d max_results=%d timeout=%.1fs",
            len(query_specs),
            max_results,
            timeout_seconds,
        )

        for query, language_code, region_code in query_specs:
            if len(hits) >= max_results:
                break
            params = {
                "engine": "youtube",
                "search_query": query,
                "sp": SERPAPI_YOUTUBE_UPLOAD_DATE_SP,
                "api_key": api_key,
            }
            if language_code:
                params["hl"] = language_code
            gl_value = self._serpapi_gl(region_code)
            if gl_value:
                params["gl"] = gl_value

            try:
                response = httpx.get(SERPAPI_YOUTUBE_ENDPOINT, params=params, timeout=timeout_seconds)
            except httpx.TimeoutException as error:
                error_count += 1
                logger.warning(
                    "SerpAPI YouTube timeout: query='%s' lang=%s region=%s error=%s",
                    query[:50],
                    language_code,
                    region_code,
                    error,
                )
                continue
            except httpx.TransportError as error:
                error_count += 1
                logger.warning(
                    "SerpAPI YouTube transport error: query='%s' lang=%s region=%s error=%s",
                    query[:50],
                    language_code,
                    region_code,
                    error,
                )
                continue

            if response.status_code >= 400:
                error_count += 1
                logger.warning(
                    "SerpAPI YouTube error response: status=%s query='%s' body=%.200s",
                    response.status_code,
                    query[:50],
                    response.text,
                )
                continue

            try:
                payload = response.json()
            except ValueError as error:
                error_count += 1
                logger.warning(
                    "SerpAPI YouTube JSON parse error: query='%s' error=%s body=%.200s",
                    query[:50],
                    error,
                    response.text,
                )
                continue

            video_ids = self._extract_video_ids(payload)
            raw_count += len(video_ids)
            for video_id in video_ids:
                if video_id in seen:
                    continue
                seen.add(video_id)
                hits.append(
                    SerpApiVideoHit(
                        video_id=video_id,
                        language_code=language_code or "en",
                        region_code=region_code,
                        query=query,
                    )
                )
                if len(hits) >= per_query_limit:
                    break

        logger.info(
            "SerpAPI YouTube discovery COMPLETE: raw=%d unique=%d errors=%d",
            raw_count,
            len(hits),
            error_count,
        )
        return SerpApiDiscoveryResult(
            hits=hits[:max_results],
            stats=SerpApiDiscoveryStats(
                query_count=len(query_specs),
                raw_count=raw_count,
                video_id_count=len(hits[:max_results]),
                error_count=error_count,
            ),
        )

    @classmethod
    def _serpapi_gl(cls, region_code: str) -> str:
        normalized = str(region_code or "").strip().upper()
        if not normalized:
            return ""
        return SERPAPI_GL_REGION_OVERRIDES.get(normalized, normalized.lower())

    @classmethod
    def _extract_video_ids(cls, payload: object) -> List[str]:
        if not isinstance(payload, dict):
            return []

        ids: List[str] = []
        seen: Set[str] = set()

        def add(value: Optional[object]) -> None:
            video_id = str(value or "").strip()
            if not video_id or video_id in seen:
                return
            seen.add(video_id)
            ids.append(video_id)

        for item in payload.get("video_results") or []:
            if isinstance(item, dict):
                add(item.get("video_id"))

        # SerpAPI can return localized flat sections like
        # "neueste_videos_von_hover_air"; include watch-page video entries
        # without pulling in nested shorts shelves or channel/category rows.
        for key, value in payload.items():
            if key in {"video_results", "shorts_results", "channel_results"}:
                continue
            if not isinstance(value, list):
                continue
            for item in value:
                if not isinstance(item, dict):
                    continue
                link = str(item.get("link") or "")
                if "/watch" not in link:
                    continue
                add(item.get("video_id"))

        return ids
