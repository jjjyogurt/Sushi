from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy.orm import Session

from app.models.video_comment import VideoComment


class VideoCommentRepository:
    def __init__(self, session: Session):
        self.session = session

    def replace_for_video(self, *, video_candidate_id: int, comments: List[dict]) -> int:
        self.session.query(VideoComment).filter(VideoComment.video_candidate_id == video_candidate_id).delete()
        if not comments:
            self.session.commit()
            return 0

        rows = [self._to_model(video_candidate_id=video_candidate_id, item=item) for item in comments]
        self.session.add_all(rows)
        self.session.commit()
        return len(rows)

    def list_texts_for_video(self, *, video_candidate_id: int, max_items: int = 5000) -> List[str]:
        rows = (
            self.session.query(VideoComment.text)
            .filter(VideoComment.video_candidate_id == video_candidate_id)
            .order_by(VideoComment.published_at.desc())
            .limit(max(1, int(max_items)))
            .all()
        )
        return [text for (text,) in rows if text]

    @staticmethod
    def _to_model(*, video_candidate_id: int, item: Dict[str, object]) -> VideoComment:
        now = datetime.now(timezone.utc)
        return VideoComment(
            video_candidate_id=video_candidate_id,
            youtube_comment_id=str(item.get("youtube_comment_id") or ""),
            parent_comment_id=str(item.get("parent_comment_id") or ""),
            author_name=str(item.get("author_name") or ""),
            text=str(item.get("text") or ""),
            like_count=max(0, int(item.get("like_count") or 0)),
            published_at=VideoCommentRepository._coerce_datetime(item.get("published_at")) or now,
            updated_at_remote=VideoCommentRepository._coerce_datetime(item.get("updated_at_remote")) or now,
            is_reply=bool(item.get("is_reply")),
        )

    @staticmethod
    def _coerce_datetime(value: object):
        if isinstance(value, datetime):
            return value
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
