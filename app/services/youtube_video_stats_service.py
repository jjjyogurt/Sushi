from __future__ import annotations

from typing import Dict, List

import requests

from app.config import get_settings


class YouTubeVideoStatsService:
    VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"

    def __init__(self):
        self.settings = get_settings()

    def fetch_view_counts(self, *, youtube_video_ids: List[str]) -> Dict[str, int]:
        ids = [str(item or "").strip() for item in youtube_video_ids if str(item or "").strip()]
        if not ids or not self.settings.youtube_data_api_key.strip():
            return {}

        unique_ids = list(dict.fromkeys(ids))
        view_counts: Dict[str, int] = {}
        timeout = max(3.0, min(30.0, float(self.settings.youtube_comments_timeout_seconds)))

        for start in range(0, len(unique_ids), 50):
            batch_ids = unique_ids[start : start + 50]
            params = {
                "part": "statistics",
                "id": ",".join(batch_ids),
                "key": self.settings.youtube_data_api_key.strip(),
                "maxResults": 50,
            }
            response = requests.get(self.VIDEOS_ENDPOINT, params=params, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            items = payload.get("items", [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                video_id = str(item.get("id", "")).strip()
                statistics = item.get("statistics", {})
                if not video_id or not isinstance(statistics, dict):
                    continue
                raw_view_count = statistics.get("viewCount", 0)
                try:
                    view_counts[video_id] = max(0, int(raw_view_count))
                except (TypeError, ValueError):
                    view_counts[video_id] = 0
        return view_counts
