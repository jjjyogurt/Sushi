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
    """Builds localized YouTube search plans from user keywords via Gemini, with deterministic fallback."""

    def __init__(self, settings: Settings, gemini_client: Optional[GeminiClient] = None):
        self.settings = settings
        self._gemini = gemini_client

    def _gemini_ready(self) -> bool:
        return self._gemini is not None and bool(self.settings.gemini_api_key.strip())

    def build_plan(self, *, keywords: List[str], languages: List[str], markets: List[str]) -> DiscoveryPlan:
        base_kw = [item.strip() for item in keywords if item and item.strip()]
        normalized_langs = YouTubeDiscoveryService._normalized_languages(languages)
        market_rows = YouTubeDiscoveryService._normalized_markets(markets)
        match_seed = list(dict.fromkeys(base_kw))

        logger.info(
            "Discovery plan build START: keywords=%d langs=%d markets=%d gemini_ready=%s",
            len(base_kw), len(normalized_langs), len(market_rows), self._gemini_ready()
        )

        if not base_kw:
            logger.warning("Discovery plan: no valid keywords provided")
            return DiscoveryPlan(query_specs=[], match_keywords=match_seed)

        if self._gemini_ready():
            try:
                logger.info("Discovery plan: calling Gemini for query expansion")
                raw = self._gemini.plan_youtube_discovery_queries(
                    keywords=base_kw,
                    language_codes=normalized_langs,
                    region_specs=[
                        {"code": code or "", "label": label}
                        for code, label in market_rows
                    ],
                )
                plan = self._plan_from_gemini_payload(raw, base_kw, normalized_langs, market_rows)
                logger.info(
                    "Discovery plan: Gemini returned queries=%d keywords=%d",
                    len(plan.query_specs), len(plan.match_keywords)
                )
                if plan.query_specs:
                    return plan
                logger.warning("Discovery plan: Gemini returned empty specs, using fallback")
            except Exception as error:  # noqa: BLE001
                logger.warning(
                    "Discovery plan: Gemini failed, using fallback. error=%s type=%s",
                    error, type(error).__name__, exc_info=True
                )
        else:
            logger.info("Discovery plan: Gemini not ready (no API key or client), using fallback")

        fallback_plan = self._fallback_plan(base_kw, normalized_langs, market_rows)
        logger.info(
            "Discovery plan FALLBACK: queries=%d keywords=%d",
            len(fallback_plan.query_specs), len(fallback_plan.match_keywords)
        )
        return fallback_plan

    def _plan_from_gemini_payload(
        self,
        parsed: dict,
        base_kw: List[str],
        normalized_langs: List[str],
        market_rows: List[Tuple[str, str]],
    ) -> DiscoveryPlan:
        fallback = self._fallback_plan(base_kw, normalized_langs, market_rows)
        queries_raw = parsed.get("queries")
        specs: List[DiscoveryQuerySpec] = list(fallback.query_specs)
        seen: Set[str] = set()
        for q, rel, reg in specs:
            seen.add(f"{rel}:{reg}:{q.lower()}")
        if isinstance(queries_raw, list):
            for item in queries_raw:
                if not isinstance(item, dict):
                    continue
                q = str(item.get("q", "")).strip()
                rel = YouTubeDiscoveryService._normalize_language_code(str(item.get("relevanceLanguage", "")))
                reg = str(item.get("regionCode", "")).strip().upper()
                if not q or len(specs) >= _MAX_SPECS:
                    continue
                if len(q) > _MAX_QUERY_CHARS:
                    q = q[:_MAX_QUERY_CHARS].rsplit(" ", 1)[0] or q[:_MAX_QUERY_CHARS]
                key = f"{rel}:{reg}:{q.lower()}"
                if key in seen:
                    continue
                seen.add(key)
                specs.append((q, rel, reg if reg else ""))

        mk = parsed.get("match_keywords")
        match_keywords: List[str] = []
        if isinstance(mk, list):
            for term in mk:
                text = str(term).strip()
                if text and text not in match_keywords:
                    match_keywords.append(text)
        for term in base_kw:
            if term not in match_keywords:
                match_keywords.append(term)

        return DiscoveryPlan(query_specs=specs[:_MAX_SPECS], match_keywords=list(dict.fromkeys(match_keywords)))

    def _fallback_plan(
        self,
        base_kw: List[str],
        normalized_langs: List[str],
        market_rows: List[Tuple[str, str]],
    ) -> DiscoveryPlan:
        query_seeds = self._query_seeds(base_kw)
        specs: List[DiscoveryQuerySpec] = []
        seen: Set[str] = set()
        for language_code in normalized_langs:
            for region_code, _market_name in market_rows:
                for query in query_seeds:
                    key = f"{language_code}:{region_code}:{query.lower()}"
                    if key in seen or len(specs) >= _MAX_SPECS:
                        continue
                    seen.add(key)
                    specs.append((query, language_code, region_code))

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
