from typing import Iterable, Tuple


class RelevanceService:
    def score(self, *, title: str, description: str, keywords: Iterable[str]) -> Tuple[float, str]:
        normalized_title = title.lower()
        normalized_description = description.lower()
        lowered_keywords = [keyword.lower().strip() for keyword in keywords if keyword.strip()]

        title_hits = [keyword for keyword in lowered_keywords if keyword in normalized_title]
        description_hits = [keyword for keyword in lowered_keywords if keyword in normalized_description]

        score = min(1.0, (len(title_hits) * 0.5) + (len(description_hits) * 0.25))
        reason_parts = []
        if title_hits:
            reason_parts.append(f"title matched: {', '.join(title_hits)}")
        if description_hits:
            reason_parts.append(f"description matched: {', '.join(description_hits)}")
        if not reason_parts:
            reason_parts.append("no direct brand keyword matched")

        return score, " | ".join(reason_parts)

