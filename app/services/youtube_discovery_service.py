from datetime import datetime, timedelta, timezone
from typing import List
from uuid import uuid5, NAMESPACE_DNS

from app.config import get_settings
from app.models.monitor_profile import MonitorProfile
from app.repositories.monitor_repository import MonitorRepository
from app.services.types import DiscoveredVideo


class YouTubeDiscoveryService:
    """Discovery service with live YouTube search and safe mock fallback."""

    def __init__(self):
        self.settings = get_settings()

    def discover(self, *, profile: MonitorProfile, max_results: int) -> List[DiscoveredVideo]:
        keywords = MonitorRepository.unpack_keywords(profile)
        languages = MonitorRepository.unpack_languages(profile)
        markets = MonitorRepository.unpack_markets(profile)
        return self.discover_by_keywords(
            keywords=keywords,
            languages=languages,
            markets=markets,
            max_results=max_results,
        )

    def discover_by_keywords(
        self, *, keywords: List[str], languages: List[str], markets: List[str], max_results: int
    ) -> List[DiscoveredVideo]:
        filtered_keywords = [item.strip() for item in keywords if item and item.strip()]

        if not self.settings.enable_mock_discovery:
            live_results = self._discover_live(
                keywords=filtered_keywords,
                languages=languages,
                markets=markets,
                max_results=max_results,
            )
            return live_results[:max_results]

        seed_videos = self._seed_videos(keywords=filtered_keywords, languages=languages, markets=markets)
        return seed_videos[:max_results]

    def _discover_live(
        self, *, keywords: List[str], languages: List[str], markets: List[str], max_results: int
    ) -> List[DiscoveredVideo]:
        try:
            import yt_dlp
        except ImportError:
            return []

        query = self._build_query(keywords=keywords, languages=languages, markets=markets)
        if not query:
            query = "product review"

        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "ignoreerrors": True,
            "noplaylist": True,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                payload = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
            results = payload.get("entries", []) if payload else []
        except Exception:  # noqa: BLE001
            return []

        discovered: List[DiscoveredVideo] = []
        default_language = languages[0] if languages else "en"
        for item in results:
            video_id = item.get("id")
            title = item.get("title")
            video_url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None
            if not video_id or not title or not video_url:
                continue

            channel = item.get("channel") or item.get("uploader") or "Unknown Channel"
            description = (item.get("description") or title).strip()
            timestamp = item.get("timestamp")
            published_at = (
                datetime.fromtimestamp(timestamp, tz=timezone.utc)
                if isinstance(timestamp, (int, float))
                else datetime.now(timezone.utc)
            )

            discovered.append(
                DiscoveredVideo(
                    youtube_video_id=video_id,
                    video_url=video_url,
                    title=title,
                    channel_name=channel,
                    language=default_language,
                    published_at=published_at,
                    description=description or title,
                )
            )
        return discovered

    @staticmethod
    def _build_query(*, keywords: List[str], languages: List[str], markets: List[str]) -> str:
        parts: List[str] = []
        if keywords:
            parts.append(" ".join(keywords[:2]))
        if markets:
            parts.append(markets[0])
        if languages:
            parts.append(languages[0])
        parts.append("review")
        return " ".join(part for part in parts if part).strip()

    def _seed_videos(self, *, keywords: List[str], languages: List[str], markets: List[str]) -> List[DiscoveredVideo]:
        default_keyword = keywords[0] if keywords else "hoverair"
        default_language = languages[0] if languages else "en"
        default_market = markets[0] if markets else "global"

        now = datetime.now(timezone.utc)
        drafts = [
            (
                f"{default_keyword} hands-on review in {default_market}",
                default_language,
                "Detailed product test with setup walkthrough and user concerns.",
                "CreatorLab",
                now - timedelta(hours=2),
            ),
            (
                f"My honest thoughts about {default_keyword} after 7 days",
                default_language,
                "Experience-focused review including battery, controls, and reliability.",
                "TechFocus",
                now - timedelta(hours=5),
            ),
            (
                f"Top mistakes people make with {default_keyword}",
                default_language,
                "Common onboarding and feature usage pain points from user comments.",
                "ReviewStation",
                now - timedelta(hours=8),
            ),
        ]

        videos: List[DiscoveredVideo] = []
        for title, language, description, channel_name, published_at in drafts:
            seed = f"{channel_name}:{title}:{published_at.isoformat()}"
            video_id = uuid5(NAMESPACE_DNS, seed).hex[:12]
            videos.append(
                DiscoveredVideo(
                    youtube_video_id=video_id,
                    video_url=f"https://www.youtube.com/watch?v={video_id}",
                    title=title,
                    channel_name=channel_name,
                    language=language,
                    published_at=published_at,
                    description=description,
                )
            )
        return videos

