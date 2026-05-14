from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Dict, List, Optional

import requests

from app.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class YouTubeVideoReachMetrics:
    view_count: Optional[int]
    subscriber_count: Optional[int]


class YouTubeVideoStatsService:
    VIDEOS_ENDPOINT = "https://www.googleapis.com/youtube/v3/videos"
    CHANNELS_ENDPOINT = "https://www.googleapis.com/youtube/v3/channels"

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

    def fetch_reach_metrics(self, *, youtube_video_ids: List[str]) -> Dict[str, YouTubeVideoReachMetrics]:
        ids = [str(item or "").strip() for item in youtube_video_ids if str(item or "").strip()]
        if not ids or not self.settings.youtube_data_api_key.strip():
            return {}

        unique_ids = list(dict.fromkeys(ids))
        video_stats_by_id: Dict[str, dict] = {}
        channel_ids: List[str] = []
        timeout = max(3.0, min(30.0, float(self.settings.youtube_comments_timeout_seconds)))

        for start in range(0, len(unique_ids), 50):
            batch_ids = unique_ids[start : start + 50]
            params = {
                "part": "statistics,snippet",
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
                snippet = item.get("snippet", {})
                channel_id = str(snippet.get("channelId", "")).strip() if isinstance(snippet, dict) else ""
                video_stats_by_id = {
                    **video_stats_by_id,
                    video_id: {
                        "view_count": self._parse_non_negative_int(statistics.get("viewCount")),
                        "channel_id": channel_id,
                    },
                }
                if channel_id:
                    channel_ids = [*channel_ids, channel_id]

        try:
            subscriber_counts_by_channel_id = self._fetch_subscriber_counts(
                channel_ids=list(dict.fromkeys(channel_ids)),
                timeout=timeout,
            )
        except Exception as error:  # noqa: BLE001
            logger.warning("youtube channel subscriber count fetch failed; continuing with views only. error=%s", error)
            subscriber_counts_by_channel_id = {}

        return {
            video_id: YouTubeVideoReachMetrics(
                view_count=stats["view_count"],
                subscriber_count=subscriber_counts_by_channel_id.get(str(stats.get("channel_id", ""))),
            )
            for video_id, stats in video_stats_by_id.items()
        }

    def _fetch_subscriber_counts(self, *, channel_ids: List[str], timeout: float) -> Dict[str, int]:
        ids = [str(item or "").strip() for item in channel_ids if str(item or "").strip()]
        if not ids:
            return {}

        subscriber_counts: Dict[str, int] = {}
        for start in range(0, len(ids), 50):
            batch_ids = ids[start : start + 50]
            params = {
                "part": "statistics",
                "id": ",".join(batch_ids),
                "key": self.settings.youtube_data_api_key.strip(),
                "maxResults": 50,
            }
            response = requests.get(self.CHANNELS_ENDPOINT, params=params, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            items = payload.get("items", [])
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                channel_id = str(item.get("id", "")).strip()
                statistics = item.get("statistics", {})
                if not channel_id or not isinstance(statistics, dict):
                    continue
                subscriber_count = self._parse_non_negative_int(statistics.get("subscriberCount"))
                if subscriber_count is not None:
                    subscriber_counts = {
                        **subscriber_counts,
                        channel_id: subscriber_count,
                    }
        return subscriber_counts

    @staticmethod
    def _parse_non_negative_int(raw_value) -> Optional[int]:
        try:
            return max(0, int(raw_value))
        except (TypeError, ValueError):
            return None
