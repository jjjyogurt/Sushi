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

        if not base_kw:
            return DiscoveryPlan(query_specs=[], match_keywords=match_seed)

        if self._gemini_ready():
            try:
                raw = self._gemini.plan_youtube_discovery_queries(
                    keywords=base_kw,
                    language_codes=normalized_langs,
                    region_specs=[
                        {"code": code or "", "label": label}
                        for code, label in market_rows
                    ],
                )
                plan = self._plan_from_gemini_payload(raw, base_kw, normalized_langs, market_rows)
                if plan.query_specs:
                    return plan
            except Exception as error:  # noqa: BLE001
                logger.warning("Gemini discovery plan failed; using fallback. error=%s", error)

        return self._fallback_plan(base_kw, normalized_langs, market_rows)

    def _plan_from_gemini_payload(
        self,
        parsed: dict,
        base_kw: List[str],
        normalized_langs: List[str],
        market_rows: List[Tuple[str, str]],
    ) -> DiscoveryPlan:
        queries_raw = parsed.get("queries")
        specs: List[DiscoveryQuerySpec] = []
        seen: Set[str] = set()
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

        expected_pairs = {(lang, code) for lang in normalized_langs for code, _label in market_rows}
        got_pairs = {(s[1], s[2]) for s in specs}
        missing = expected_pairs - got_pairs
        if missing:
            fallback = self._fallback_plan(base_kw, normalized_langs, market_rows)
            for spec in fallback.query_specs:
                pair = (spec[1], spec[2])
                if pair in missing and spec not in specs and len(specs) < _MAX_SPECS:
                    specs.append(spec)

        return DiscoveryPlan(query_specs=specs[:_MAX_SPECS], match_keywords=list(dict.fromkeys(match_keywords)))

    def _fallback_plan(
        self,
        base_kw: List[str],
        normalized_langs: List[str],
        market_rows: List[Tuple[str, str]],
    ) -> DiscoveryPlan:
        q_base = " ".join(base_kw).strip()
        if len(q_base) > _MAX_QUERY_CHARS:
            q_base = q_base[:_MAX_QUERY_CHARS].rsplit(" ", 1)[0] or q_base[:_MAX_QUERY_CHARS]

        specs: List[DiscoveryQuerySpec] = []
        seen: Set[str] = set()
        for language_code in normalized_langs:
            for region_code, _market_name in market_rows:
                key = f"{language_code}:{region_code}:{q_base.lower()}"
                if key in seen or len(specs) >= _MAX_SPECS:
                    continue
                seen.add(key)
                specs.append((q_base, language_code, region_code))

        return DiscoveryPlan(query_specs=specs, match_keywords=list(dict.fromkeys(base_kw)))
