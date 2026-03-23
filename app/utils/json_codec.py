import json
from typing import Any


def encode_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True)


def decode_json(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback

