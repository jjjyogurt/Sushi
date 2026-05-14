from datetime import datetime, timezone

from app.models.analysis_result import AnalysisResult
from app.models.enums import AnalysisStatus, RiskLevel, Sentiment
from app.models.video_candidate import VideoCandidate
from app.services.analysis_batch_service import AnalysisBatchService
from app.utils.text import normalize_title, title_fingerprint


def _create_video(db_session, monitor_profile, *, youtube_video_id: str, title: str) -> VideoCandidate:
    video = VideoCandidate(
        monitor_profile_id=monitor_profile.id,
        youtube_video_id=youtube_video_id,
        video_url=f"https://www.youtube.com/watch?v={youtube_video_id}",
        title=title,
        normalized_title=normalize_title(title),
        title_fingerprint=title_fingerprint(title),
        channel_name="Creator",
        language="en",
        published_at=datetime.now(timezone.utc),
        relevance_score=0.8,
        relevance_reason="seed",
    )
    db_session.add(video)
    db_session.commit()
    db_session.refresh(video)
    return video


def _create_completed_analysis(db_session, video: VideoCandidate) -> None:
    db_session.add(
        AnalysisResult(
            video_candidate_id=video.id,
            analysis_version="v1",
            language="en",
            model_name="test-model",
            status=AnalysisStatus.COMPLETED,
            transcript_text="transcript",
            summary_text="summary",
            translated_summary="summary",
            sentiment=Sentiment.NEUTRAL,
            risk_level=RiskLevel.LOW,
            confidence_score="0.8",
            evidence_json="[]",
            insights_json="{}",
            error_message="",
        )
    )
    db_session.commit()


def test_create_batch_includes_discovered_project_videos(db_session, monitor_profile):
    first = _create_video(db_session, monitor_profile, youtube_video_id="batch-discovered-1", title="First")
    second = _create_video(db_session, monitor_profile, youtube_video_id="batch-discovered-2", title="Second")

    batch = AnalysisBatchService(db_session).create_batch(
        monitor_profile_id=monitor_profile.id,
        created_by=monitor_profile.owner_user_id,
    )

    assert batch.total_count == 2
    assert sorted(item.video_id for item in batch.items) == [first.id, second.id]


def test_create_batch_skips_completed_discovered_videos(db_session, monitor_profile):
    completed = _create_video(db_session, monitor_profile, youtube_video_id="batch-completed", title="Completed")
    pending = _create_video(db_session, monitor_profile, youtube_video_id="batch-pending", title="Pending")
    _create_completed_analysis(db_session, completed)

    batch = AnalysisBatchService(db_session).create_batch(
        monitor_profile_id=monitor_profile.id,
        created_by=monitor_profile.owner_user_id,
    )

    assert batch.total_count == 1
    assert [item.video_id for item in batch.items] == [pending.id]
