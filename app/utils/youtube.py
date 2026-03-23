import json
import re
import urllib.parse
import urllib.request


VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{11}$")


def extract_video_id(url_or_id: str) -> str:
    value = url_or_id.strip()
    if VIDEO_ID_PATTERN.fullmatch(value):
        return value

    parsed = urllib.parse.urlparse(value)
    if parsed.netloc in {"youtu.be", "www.youtu.be"}:
        candidate = parsed.path.lstrip("/").split("/")[0]
        if VIDEO_ID_PATTERN.fullmatch(candidate):
            return candidate

    if "youtube.com" in parsed.netloc:
        query = urllib.parse.parse_qs(parsed.query)
        candidate = (query.get("v") or [""])[0]
        if VIDEO_ID_PATTERN.fullmatch(candidate):
            return candidate

        path_parts = [part for part in parsed.path.split("/") if part]
        if len(path_parts) >= 2 and path_parts[0] in {"shorts", "live"}:
            candidate = path_parts[1]
            if VIDEO_ID_PATTERN.fullmatch(candidate):
                return candidate

    raise ValueError("Invalid YouTube URL or video id.")


def fetch_oembed_metadata(video_url: str):
    endpoint = "https://www.youtube.com/oembed"
    query = urllib.parse.urlencode({"url": video_url, "format": "json"})
    target = f"{endpoint}?{query}"
    with urllib.request.urlopen(target, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    return {
        "title": payload.get("title") or "YouTube video",
        "channel_name": payload.get("author_name") or "Unknown Channel",
    }

