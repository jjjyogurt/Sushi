from datetime import datetime
from typing import Dict, List, Optional

import httpx

from app.config import get_settings


class YouTubeCommentsService:
    def __init__(self):
        self.settings = get_settings()

    def fetch_all_comments(self, *, youtube_video_id: str) -> List[Dict[str, object]]:
        api_key = self.settings.youtube_data_api_key.strip()
        if not api_key:
            return []

        top_level_items = self._fetch_top_level_threads(youtube_video_id=youtube_video_id, api_key=api_key)
        comments: List[Dict[str, object]] = []

        for thread in top_level_items:
            top_level = self._extract_top_level_comment(thread=thread)
            if top_level:
                comments = [*comments, top_level]

            snippet = thread.get("snippet") if isinstance(thread, dict) else {}
            total_reply_count = self._safe_int((snippet or {}).get("totalReplyCount"))
            parent_id = str(((top_level or {}).get("youtube_comment_id")) or "")
            if total_reply_count <= 0 or not parent_id:
                continue
            replies = self._fetch_replies(parent_id=parent_id, api_key=api_key)
            comments = [*comments, *replies]
        return comments

    def _fetch_top_level_threads(self, *, youtube_video_id: str, api_key: str) -> List[Dict[str, object]]:
        endpoint = "https://www.googleapis.com/youtube/v3/commentThreads"
        page_token = ""
        collected: List[Dict[str, object]] = []
        max_pages = max(1, int(self.settings.youtube_comments_max_pages))

        for _ in range(max_pages):
            params = {
                "part": "snippet",
                "videoId": youtube_video_id,
                "textFormat": "plainText",
                "maxResults": max(1, min(100, int(self.settings.youtube_comments_page_size))),
                "order": "time",
                "key": api_key,
            }
            if page_token:
                params = {**params, "pageToken": page_token}
            payload = self._request_json(url=endpoint, params=params)
            items = payload.get("items")
            if isinstance(items, list):
                collected = [*collected, *[item for item in items if isinstance(item, dict)]]
            page_token = str(payload.get("nextPageToken") or "").strip()
            if not page_token:
                break
        return collected

    def _fetch_replies(self, *, parent_id: str, api_key: str) -> List[Dict[str, object]]:
        endpoint = "https://www.googleapis.com/youtube/v3/comments"
        page_token = ""
        collected: List[Dict[str, object]] = []
        max_pages = max(1, int(self.settings.youtube_comments_max_reply_pages))

        for _ in range(max_pages):
            params = {
                "part": "snippet",
                "parentId": parent_id,
                "textFormat": "plainText",
                "maxResults": max(1, min(100, int(self.settings.youtube_comments_page_size))),
                "key": api_key,
            }
            if page_token:
                params = {**params, "pageToken": page_token}
            payload = self._request_json(url=endpoint, params=params)
            items = payload.get("items")
            if isinstance(items, list):
                parsed = [self._extract_reply_comment(item=item, parent_id=parent_id) for item in items]
                collected = [*collected, *[item for item in parsed if item]]
            page_token = str(payload.get("nextPageToken") or "").strip()
            if not page_token:
                break
        return collected

    def _request_json(self, *, url: str, params: Dict[str, object]) -> Dict[str, object]:
        retries = max(0, int(self.settings.youtube_comments_max_retries))
        timeout = max(1.0, float(self.settings.youtube_comments_timeout_seconds))
        last_error: Optional[Exception] = None
        for _ in range(retries + 1):
            try:
                response = httpx.get(url, params=params, timeout=timeout)
            except (httpx.TimeoutException, httpx.TransportError) as error:
                last_error = error
                continue
            if response.status_code >= 400:
                # If comments are disabled/forbidden, return an empty result for this source.
                if response.status_code in {403, 404}:
                    return {}
                response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                return payload
            return {}
        if last_error:
            raise RuntimeError(f"YouTube comments request failed: {last_error}") from last_error
        return {}

    def _extract_top_level_comment(self, *, thread: Dict[str, object]) -> Optional[Dict[str, object]]:
        snippet = thread.get("snippet")
        if not isinstance(snippet, dict):
            return None
        top_level_comment = snippet.get("topLevelComment")
        if not isinstance(top_level_comment, dict):
            return None
        comment_snippet = top_level_comment.get("snippet")
        if not isinstance(comment_snippet, dict):
            return None
        comment_id = str(top_level_comment.get("id") or "").strip()
        text = str(comment_snippet.get("textDisplay") or "").strip()
        if not comment_id or not text:
            return None
        return {
            "youtube_comment_id": comment_id,
            "parent_comment_id": "",
            "author_name": str(comment_snippet.get("authorDisplayName") or "").strip(),
            "text": text,
            "like_count": self._safe_int(comment_snippet.get("likeCount")),
            "published_at": self._parse_datetime(comment_snippet.get("publishedAt")),
            "updated_at_remote": self._parse_datetime(comment_snippet.get("updatedAt")),
            "is_reply": False,
        }

    def _extract_reply_comment(self, *, item: Dict[str, object], parent_id: str) -> Optional[Dict[str, object]]:
        snippet = item.get("snippet")
        if not isinstance(snippet, dict):
            return None
        comment_id = str(item.get("id") or "").strip()
        text = str(snippet.get("textDisplay") or "").strip()
        if not comment_id or not text:
            return None
        return {
            "youtube_comment_id": comment_id,
            "parent_comment_id": parent_id,
            "author_name": str(snippet.get("authorDisplayName") or "").strip(),
            "text": text,
            "like_count": self._safe_int(snippet.get("likeCount")),
            "published_at": self._parse_datetime(snippet.get("publishedAt")),
            "updated_at_remote": self._parse_datetime(snippet.get("updatedAt")),
            "is_reply": True,
        }

    @staticmethod
    def _safe_int(value: object) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _parse_datetime(value: object):
        if not value:
            return None
        raw = str(value).strip()
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
