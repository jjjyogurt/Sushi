from dataclasses import dataclass
from typing import List, Tuple

# (query, relevanceLanguage, regionCode) — regionCode may be "" for global
DiscoveryQuerySpec = Tuple[str, str, str]


@dataclass(frozen=True)
class DiscoveryPlan:
    """YouTube discovery: API query strings plus keywords used to filter/score results."""

    query_specs: List[DiscoveryQuerySpec]
    match_keywords: List[str]
