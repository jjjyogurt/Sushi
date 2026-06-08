import logging
from typing import List, Optional, Set, Tuple

from app.config import Settings
from app.services.discovery_types import DiscoveryPlan, DiscoveryQuerySpec
from app.services.gemini_client import GeminiClient
from app.services.youtube_discovery_service import YouTubeDiscoveryService

logger = logging.getLogger(__name__)

_MAX_QUERY_CHARS = 100
_MAX_SPECS = 24


class DiscoveryKeywordService:
    """Builds deterministic YouTube search plans from user-defined project keywords."""

    def __init__(self, settings: Settings, gemini_client: Optional[GeminiClient] = None):
        self.settings = settings
        self._gemini = gemini_client

    def build_plan(self, *, keywords: List[str], languages: List[str], markets: List[str]) -> DiscoveryPlan:
        base_kw = [item.strip() for item in keywords if item and item.strip()]
        normalized_langs = YouTubeDiscoveryService._normalized_languages(languages)
        market_rows = YouTubeDiscoveryService._normalized_markets(markets)
        match_seed = list(dict.fromkeys(base_kw))

        logger.info(
            "Discovery plan build START: keywords=%d langs=%d markets=%d strategy=exact_keywords",
            len(base_kw), len(normalized_langs), len(market_rows)
        )

        if not base_kw:
            logger.warning("Discovery plan: no valid keywords provided")
            return DiscoveryPlan(query_specs=[], match_keywords=match_seed)

        fallback_plan = self._fallback_plan(base_kw, normalized_langs, market_rows)
        logger.info(
            "Discovery plan COMPLETE: queries=%d keywords=%d",
            len(fallback_plan.query_specs), len(fallback_plan.match_keywords)
        )
        return fallback_plan

    def _fallback_plan(
        self,
        base_kw: List[str],
        normalized_langs: List[str],
        market_rows: List[Tuple[str, str]],
    ) -> DiscoveryPlan:
        query_seeds = self._query_seeds(base_kw)
        specs: List[DiscoveryQuerySpec] = []
        seen: Set[str] = set()

        def add_spec(*, query: str, language_code: str, region_code: str) -> None:
            key = f"{language_code}:{region_code}:{query.lower()}"
            if key in seen or len(specs) >= _MAX_SPECS:
                return
            seen.add(key)
            specs.append((query, language_code, region_code))

        for language_code in normalized_langs:
            for region_code, _market_name in market_rows:
                for query in query_seeds:
                    add_spec(query=query, language_code=language_code, region_code=region_code)

        return DiscoveryPlan(query_specs=specs, match_keywords=list(dict.fromkeys(base_kw)))

    @staticmethod
    def _query_seeds(base_kw: List[str]) -> List[str]:
        seeds: List[str] = []
        for keyword in base_kw:
            query = str(keyword or "").strip()
            if not query:
                continue
            if len(query) > _MAX_QUERY_CHARS:
                query = query[:_MAX_QUERY_CHARS].rsplit(" ", 1)[0] or query[:_MAX_QUERY_CHARS]
            if query and query not in seeds:
                seeds.append(query)
        return seeds
