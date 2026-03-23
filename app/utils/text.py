import re


def normalize_title(value: str) -> str:
    lowered = value.lower().strip()
    collapsed = re.sub(r"\s+", " ", lowered)
    return collapsed


def title_fingerprint(value: str) -> str:
    normalized = normalize_title(value)
    alnum = re.sub(r"[^a-z0-9 ]", "", normalized)
    tokens = [token for token in alnum.split(" ") if token]
    return "-".join(tokens[:12])

