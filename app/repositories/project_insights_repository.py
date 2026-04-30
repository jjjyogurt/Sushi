from typing import List, Optional, Sequence, Tuple

from sqlalchemy import and_, desc, func
from sqlalchemy.orm import Session

from app.models.analysis_result import AnalysisResult
from app.models.project_insight_report import ProjectInsightReport
from app.models.video_candidate import VideoCandidate


class ProjectInsightsRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        monitor_profile_id: int,
        analyzed_video_count: int,
        total_video_count: int,
        excluded_video_count: int,
        coverage_pct: float,
        overall_sentiment: str,
        risk_level: str,
        risk_score: float,
        summary_headline: str,
        summary_body: str,
        praise_points_json: str,
        criticism_points_json: str,
        user_recommendations_json: str,
        excluded_reasons_json: str,
        sentiment_breakdown_json: str,
        risk_breakdown_json: str,
        reach_metrics_json: str,
        top_negative_videos_json: str,
        report_markdown: str,
    ) -> ProjectInsightReport:
        report = ProjectInsightReport(
            monitor_profile_id=monitor_profile_id,
            analyzed_video_count=analyzed_video_count,
            total_video_count=total_video_count,
            excluded_video_count=excluded_video_count,
            coverage_pct=coverage_pct,
            overall_sentiment=overall_sentiment,
            risk_level=risk_level,
            risk_score=risk_score,
            summary_headline=summary_headline,
            summary_body=summary_body,
            praise_points_json=praise_points_json,
            criticism_points_json=criticism_points_json,
            user_recommendations_json=user_recommendations_json,
            excluded_reasons_json=excluded_reasons_json,
            sentiment_breakdown_json=sentiment_breakdown_json,
            risk_breakdown_json=risk_breakdown_json,
            reach_metrics_json=reach_metrics_json,
            top_negative_videos_json=top_negative_videos_json,
            report_markdown=report_markdown,
        )
        self.session.add(report)
        self.session.commit()
        self.session.refresh(report)
        return report

    def get_latest_for_profile(self, monitor_profile_id: int) -> Optional[ProjectInsightReport]:
        return (
            self.session.query(ProjectInsightReport)
            .filter(ProjectInsightReport.monitor_profile_id == monitor_profile_id)
            .order_by(desc(ProjectInsightReport.created_at), desc(ProjectInsightReport.id))
            .first()
        )

    def list_for_profile(self, monitor_profile_id: int, *, limit: int = 20) -> List[ProjectInsightReport]:
        return (
            self.session.query(ProjectInsightReport)
            .filter(ProjectInsightReport.monitor_profile_id == monitor_profile_id)
            .order_by(desc(ProjectInsightReport.created_at), desc(ProjectInsightReport.id))
            .limit(limit)
            .all()
        )

    def get_by_id_for_profile(self, *, monitor_profile_id: int, report_id: int) -> Optional[ProjectInsightReport]:
        return (
            self.session.query(ProjectInsightReport)
            .filter(ProjectInsightReport.monitor_profile_id == monitor_profile_id)
            .filter(ProjectInsightReport.id == report_id)
            .one_or_none()
        )

    def list_videos_with_latest_analysis(
        self,
        *,
        monitor_profile_id: int,
        language: str = "en",
    ) -> Sequence[Tuple[VideoCandidate, Optional[AnalysisResult]]]:
        latest_analysis_subquery = (
            self.session.query(
                AnalysisResult.video_candidate_id.label("video_candidate_id"),
                func.max(AnalysisResult.created_at).label("max_created_at"),
            )
            .join(VideoCandidate, VideoCandidate.id == AnalysisResult.video_candidate_id)
            .filter(VideoCandidate.monitor_profile_id == monitor_profile_id)
            .filter(AnalysisResult.language == language)
            .group_by(AnalysisResult.video_candidate_id)
            .subquery()
        )

        return (
            self.session.query(VideoCandidate, AnalysisResult)
            .outerjoin(
                latest_analysis_subquery,
                latest_analysis_subquery.c.video_candidate_id == VideoCandidate.id,
            )
            .outerjoin(
                AnalysisResult,
                and_(
                    AnalysisResult.video_candidate_id == latest_analysis_subquery.c.video_candidate_id,
                    AnalysisResult.created_at == latest_analysis_subquery.c.max_created_at,
                    AnalysisResult.language == language,
                ),
            )
            .filter(VideoCandidate.monitor_profile_id == monitor_profile_id)
            .order_by(desc(VideoCandidate.published_at))
            .all()
        )

    def delete_by_id_for_profile(self, *, monitor_profile_id: int, report_id: int) -> int:
        deleted = (
            self.session.query(ProjectInsightReport)
            .filter(ProjectInsightReport.monitor_profile_id == monitor_profile_id)
            .filter(ProjectInsightReport.id == report_id)
            .delete(synchronize_session=False)
        )
        self.session.commit()
        return int(deleted)

    def delete_for_profile(self, monitor_profile_id: int) -> int:
        deleted = self.session.query(ProjectInsightReport).filter(
            ProjectInsightReport.monitor_profile_id == monitor_profile_id
        ).delete(synchronize_session=False)
        self.session.commit()
        return int(deleted)
