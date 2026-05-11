from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional
import logging

from app.config import get_settings
from app.services.agent_settings_service import AgentSettingsService
from app.services.gemini_client import GeminiClient
from app.models.enums import AnalysisStatus
from app.models.project_insight_report import ProjectInsightReport
from app.repositories.monitor_repository import MonitorRepository
from app.repositories.project_insights_repository import ProjectInsightsRepository
from app.services.youtube_video_stats_service import YouTubeVideoStatsService
from app.utils.json_codec import decode_json, encode_json

logger = logging.getLogger(__name__)


class ProjectInsightsService:
    RISK_SCORE_BY_LEVEL: Dict[str, float] = {
        "low": 2.0,
        "medium": 5.0,
        "high": 8.0,
        "critical": 10.0,
    }

    def __init__(self, session):
        self.monitor_repository = MonitorRepository(session)
        self.repository = ProjectInsightsRepository(session)
        self.settings = get_settings()
        self.agent_settings_service = AgentSettingsService()
        self.gemini_client = GeminiClient(self.settings)
        self.youtube_video_stats_service = YouTubeVideoStatsService()

    def get_current_report(self, monitor_profile_id: int) -> Optional[ProjectInsightReport]:
        self._require_profile(monitor_profile_id)
        return self.repository.get_latest_for_profile(monitor_profile_id)

    def list_report_history(self, monitor_profile_id: int, *, limit: int = 20) -> List[ProjectInsightReport]:
        self._require_profile(monitor_profile_id)
        return self.repository.list_for_profile(monitor_profile_id, limit=limit)

    def refresh_report(self, monitor_profile_id: int) -> ProjectInsightReport:
        profile = self._require_profile(monitor_profile_id)
        brand_keywords = self.monitor_repository.unpack_keywords(profile)
        key_products = self.monitor_repository.unpack_key_products(profile)
        video_analysis_pairs = self.repository.list_videos_with_latest_analysis(
            monitor_profile_id=monitor_profile_id,
            language="en",
        )

        total_video_count = len(video_analysis_pairs)
        completed_results = []
        completed_video_rows = []
        excluded_reason_counter: Counter[str] = Counter()

        for _video, analysis in video_analysis_pairs:
            if analysis is None:
                excluded_reason_counter["analysis_missing"] += 1
                continue
            if analysis.status != AnalysisStatus.COMPLETED:
                excluded_reason_counter["analysis_not_completed"] += 1
                continue
            if not str(analysis.transcript_text or "").strip():
                excluded_reason_counter["transcript_missing_in_db"] += 1
                continue
            completed_results = [*completed_results, analysis]
            completed_video_rows = [*completed_video_rows, (_video, analysis)]

        analyzed_video_count = len(completed_results)
        excluded_video_count = max(0, total_video_count - analyzed_video_count)
        coverage_pct = round((analyzed_video_count / total_video_count) * 100, 1) if total_video_count > 0 else 0.0
        excluded_reasons = [
            f"{reason}:{count}" for reason, count in excluded_reason_counter.most_common() if count > 0
        ]

        if analyzed_video_count == 0:
            payload = self._empty_payload(total_video_count=total_video_count)
        else:
            fallback_payload = self._build_payload(completed_video_rows)
            payload = self._build_payload_with_gemini(
                profile_name=str(profile.name or "").strip() or f"Project {monitor_profile_id}",
                brand_keywords=brand_keywords,
                key_products=key_products,
                total_video_count=total_video_count,
                analyzed_video_count=analyzed_video_count,
                completed_results=completed_results,
                fallback_payload=fallback_payload,
            )

        generated_at = datetime.now(timezone.utc)
        report_markdown = self._build_markdown_report(
            generated_at=generated_at,
            analyzed_video_count=analyzed_video_count,
            total_video_count=total_video_count,
            coverage_pct=coverage_pct,
            payload=payload,
            excluded_reasons=excluded_reasons,
        )

        return self.repository.create(
            monitor_profile_id=monitor_profile_id,
            analyzed_video_count=analyzed_video_count,
            total_video_count=total_video_count,
            excluded_video_count=excluded_video_count,
            coverage_pct=coverage_pct,
            overall_sentiment=payload["overall_sentiment"],
            risk_level=payload["risk_level"],
            risk_score=payload["risk_score"],
            summary_headline=payload["summary_headline"],
            summary_body=payload["summary_body"],
            praise_points_json=encode_json(payload["praise_points"]),
            criticism_points_json=encode_json(payload["criticism_points"]),
            user_recommendations_json=encode_json(payload["user_recommendations"]),
            excluded_reasons_json=encode_json(excluded_reasons),
            sentiment_breakdown_json=encode_json(payload["sentiment_breakdown"]),
            risk_breakdown_json=encode_json(payload["risk_breakdown"]),
            reach_metrics_json=encode_json(payload["reach_metrics"]),
            top_negative_videos_json=encode_json(payload["top_negative_videos"]),
            report_markdown=report_markdown,
        )

    def _build_payload_with_gemini(
        self,
        *,
        profile_name: str,
        brand_keywords: List[str],
        key_products: List[str],
        total_video_count: int,
        analyzed_video_count: int,
        completed_results,
        fallback_payload: Dict[str, object],
    ) -> Dict[str, object]:
        records = self._build_gemini_records(completed_results)
        if len(records) == 0:
            return fallback_payload
        agent_instructions = self.agent_settings_service.get_content()
        try:
            generated = self.gemini_client.generate_project_insights_report(
                project_name=profile_name,
                brand_keywords=brand_keywords,
                key_products=key_products,
                total_video_count=total_video_count,
                analyzed_video_count=analyzed_video_count,
                records=records,
                agent_instructions=agent_instructions,
            )
        except Exception as error:  # noqa: BLE001
            logger.warning("project insights Gemini synthesis failed; falling back to deterministic payload. error=%s", error)
            return fallback_payload

        merged_payload = {
            **fallback_payload,
            "summary_headline": generated.get("summary_headline") or fallback_payload.get("summary_headline", ""),
            "summary_body": generated.get("summary_body") or fallback_payload.get("summary_body", ""),
            "top_risk_trigger": generated.get("top_risk_trigger") or fallback_payload.get("top_risk_trigger", ""),
            "overall_sentiment": generated.get("overall_sentiment") or fallback_payload.get("overall_sentiment", "neutral"),
            "risk_level": generated.get("risk_level") or fallback_payload.get("risk_level", "medium"),
            "risk_score": generated.get("risk_score") if generated.get("risk_score") is not None else fallback_payload.get("risk_score", 0.0),
            "praise_points": generated.get("praise_points") or fallback_payload.get("praise_points", []),
            "criticism_points": generated.get("criticism_points") or fallback_payload.get("criticism_points", []),
            "user_recommendations": generated.get("user_recommendations") or fallback_payload.get("user_recommendations", []),
        }
        return merged_payload

    def delete_history_item(self, *, monitor_profile_id: int, report_id: int) -> int:
        self._require_profile(monitor_profile_id)
        existing = self.repository.get_by_id_for_profile(
            monitor_profile_id=monitor_profile_id,
            report_id=report_id,
        )
        if existing is None:
            raise ValueError("Insights report not found.")
        return self.repository.delete_by_id_for_profile(
            monitor_profile_id=monitor_profile_id,
            report_id=report_id,
        )

    def clear_history(self, monitor_profile_id: int) -> int:
        self._require_profile(monitor_profile_id)
        return self.repository.delete_for_profile(monitor_profile_id)

    def _require_profile(self, monitor_profile_id: int):
        profile = self.monitor_repository.get(monitor_profile_id)
        if profile is None:
            raise ValueError("Monitor profile not found.")
        return profile

    def _build_payload(self, completed_video_rows) -> Dict[str, object]:
        sentiment_counter: Counter[str] = Counter()
        risk_counter: Counter[str] = Counter()
        praise_counter: Counter[str] = Counter()
        criticism_counter: Counter[str] = Counter()
        recommendation_counter: Counter[str] = Counter()
        headline_samples: List[str] = []
        reached_by_sentiment: Dict[str, int] = {"positive": 0, "neutral": 0, "negative": 0}
        reached_by_risk: Dict[str, int] = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        negative_videos_by_reach: List[dict] = []

        youtube_video_ids = [video.youtube_video_id for video, _analysis in completed_video_rows]
        view_counts_by_video_id: Dict[str, int] = {}
        try:
            view_counts_by_video_id = self.youtube_video_stats_service.fetch_view_counts(youtube_video_ids=youtube_video_ids)
        except Exception as error:  # noqa: BLE001
            logger.warning("project insights reach metrics fetch failed; continuing with zeroed view counts. error=%s", error)

        risk_total = 0.0
        for video, result in completed_video_rows:
            sentiment_value = getattr(result.sentiment, "value", str(result.sentiment or "neutral")).lower()
            risk_value = getattr(result.risk_level, "value", str(result.risk_level or "low")).lower()
            sentiment_counter[sentiment_value] += 1
            risk_counter[risk_value] += 1
            risk_total += self.RISK_SCORE_BY_LEVEL.get(risk_value, 5.0)
            view_count = max(0, int(view_counts_by_video_id.get(video.youtube_video_id, 0)))
            if sentiment_value in reached_by_sentiment:
                reached_by_sentiment[sentiment_value] += view_count
            if risk_value in reached_by_risk:
                reached_by_risk[risk_value] += view_count
            if sentiment_value == "negative":
                negative_videos_by_reach = [
                    *negative_videos_by_reach,
                    {
                        "video_id": int(video.id),
                        "youtube_video_id": video.youtube_video_id,
                        "title": str(video.title or ""),
                        "channel_name": str(video.channel_name or ""),
                        "view_count": view_count,
                        "risk_level": risk_value,
                    },
                ]

            insights_payload = decode_json(result.insights_json, {})
            parsed = self._parse_insights_payload(insights_payload)
            for point in parsed["praise_points"]:
                praise_counter[point] += 1
            for point in parsed["criticism_points"]:
                criticism_counter[point] += 1
            for recommendation in parsed["user_recommendations"]:
                recommendation_counter[recommendation] += 1

            summary_headline = str(result.summary_headline or "").strip()
            if summary_headline:
                headline_samples = [*headline_samples, summary_headline]

        analyzed_count = len(completed_video_rows)
        overall_sentiment = self._top_label(sentiment_counter, fallback="neutral")
        average_risk_score = round((risk_total / analyzed_count), 1) if analyzed_count > 0 else 0.0
        risk_level = self._risk_level_from_score(average_risk_score)
        praise_points = [item for item, _count in praise_counter.most_common(5)]
        criticism_points = [item for item, _count in criticism_counter.most_common(5)]
        user_recommendations = [item for item, _count in recommendation_counter.most_common(5)]

        summary_headline = (
            f"{analyzed_count} analyzed videos show {overall_sentiment} sentiment and {risk_level} risk signals."
        )
        if headline_samples:
            summary_headline = headline_samples[0]

        summary_body = self._build_summary_body(
            analyzed_count=analyzed_count,
            overall_sentiment=overall_sentiment,
            risk_level=risk_level,
            praise_points=praise_points,
            criticism_points=criticism_points,
            user_recommendations=user_recommendations,
        )
        top_risk_trigger = criticism_points[0] if criticism_points else "No recurring critical trigger identified yet."
        sentiment_breakdown = {
            "positive": int(sentiment_counter.get("positive", 0)),
            "neutral": int(sentiment_counter.get("neutral", 0)),
            "negative": int(sentiment_counter.get("negative", 0)),
        }
        risk_breakdown = {
            "low": int(risk_counter.get("low", 0)),
            "medium": int(risk_counter.get("medium", 0)),
            "high": int(risk_counter.get("high", 0)),
            "critical": int(risk_counter.get("critical", 0)),
        }
        total_reach_views = int(sum(reached_by_sentiment.values()))
        negative_reach_views = int(reached_by_sentiment.get("negative", 0))
        critical_risk_reach = int(reached_by_risk.get("high", 0) + reached_by_risk.get("critical", 0))
        negative_reach_share_pct = round((negative_reach_views / total_reach_views) * 100, 1) if total_reach_views > 0 else 0.0
        top_negative_videos = sorted(negative_videos_by_reach, key=lambda item: int(item.get("view_count", 0)), reverse=True)[:5]
        action_required = "monitor"
        if risk_breakdown["critical"] > 0 or risk_breakdown["high"] >= 3 or negative_reach_share_pct >= 35.0:
            action_required = "act_now"
        elif risk_breakdown["high"] > 0 or risk_breakdown["medium"] >= 3:
            action_required = "monitor"
        else:
            action_required = "no_action"
        reach_metrics = {
            "total_reach_views": total_reach_views,
            "negative_reach_views": negative_reach_views,
            "negative_reach_share_pct": negative_reach_share_pct,
            "critical_risk_reach": critical_risk_reach,
            "action_required": action_required,
        }

        return {
            "overall_sentiment": overall_sentiment,
            "risk_level": risk_level,
            "risk_score": average_risk_score,
            "summary_headline": summary_headline,
            "summary_body": summary_body,
            "top_risk_trigger": top_risk_trigger,
            "praise_points": praise_points,
            "criticism_points": criticism_points,
            "user_recommendations": user_recommendations,
            "sentiment_breakdown": sentiment_breakdown,
            "risk_breakdown": risk_breakdown,
            "reach_metrics": reach_metrics,
            "top_negative_videos": top_negative_videos,
        }

    @staticmethod
    def _build_gemini_records(completed_results) -> List[dict]:
        max_videos = 80
        records: List[dict] = []

        for result in completed_results[:max_videos]:
            transcript = str(result.transcript_text or "").strip()
            insights_payload = decode_json(result.insights_json, {})
            parsed = ProjectInsightsService._parse_insights_payload(insights_payload)
            evidence = decode_json(result.evidence_json, [])
            record = {
                "video_id": int(result.video_candidate_id),
                "summary_headline": str(result.summary_headline or "").strip(),
                "summary_body": str(result.summary_body or "").strip(),
                "sentiment": getattr(result.sentiment, "value", str(result.sentiment or "neutral")).lower(),
                "risk_level": getattr(result.risk_level, "value", str(result.risk_level or "medium")).lower(),
                "praise_points": parsed["praise_points"],
                "criticism_points": parsed["criticism_points"],
                "action_recommendation": parsed["user_recommendations"][0] if parsed["user_recommendations"] else "",
                "evidence": evidence if isinstance(evidence, list) else [],
                "transcript_full": transcript,
            }
            records = [*records, record]
        return records

    @staticmethod
    def _parse_insights_payload(payload) -> Dict[str, List[str]]:
        if isinstance(payload, dict):
            praise_points = ProjectInsightsService._normalize_point_list(payload.get("praise_points", []))
            criticism_points = ProjectInsightsService._normalize_point_list(payload.get("criticism_points", []))
            recommendation = str(payload.get("action_recommendation", "")).strip()
            user_recommendations = [recommendation] if recommendation else []
            return {
                "praise_points": praise_points,
                "criticism_points": criticism_points,
                "user_recommendations": user_recommendations,
            }
        if isinstance(payload, list):
            legacy_items = ProjectInsightsService._normalize_point_list(payload)
            return {
                "praise_points": [],
                "criticism_points": legacy_items[:5],
                "user_recommendations": [],
            }
        return {
            "praise_points": [],
            "criticism_points": [],
            "user_recommendations": [],
            "sentiment_breakdown": {"positive": 0, "neutral": 0, "negative": 0},
            "risk_breakdown": {"low": 0, "medium": 0, "high": 0, "critical": 0},
            "reach_metrics": {
                "total_reach_views": 0,
                "negative_reach_views": 0,
                "negative_reach_share_pct": 0.0,
                "critical_risk_reach": 0,
                "action_required": "no_action",
            },
            "top_negative_videos": [],
        }

    @staticmethod
    def _normalize_point_list(values) -> List[str]:
        if not isinstance(values, list):
            return []
        normalized: List[str] = []
        for item in values:
            text = str(item or "").strip()
            if not text or text in normalized:
                continue
            normalized = [*normalized, text]
        return normalized

    @staticmethod
    def _top_label(counter: Counter[str], *, fallback: str) -> str:
        if not counter:
            return fallback
        return counter.most_common(1)[0][0]

    @staticmethod
    def _risk_level_from_score(score: float) -> str:
        if score >= 8.5:
            return "critical"
        if score >= 6.5:
            return "high"
        if score >= 3.5:
            return "medium"
        return "low"

    @staticmethod
    def _build_summary_body(
        *,
        analyzed_count: int,
        overall_sentiment: str,
        risk_level: str,
        praise_points: List[str],
        criticism_points: List[str],
        user_recommendations: List[str],
    ) -> str:
        top_praise = praise_points[0] if praise_points else "No consistent praise theme yet."
        top_criticism = criticism_points[0] if criticism_points else "No recurring criticism theme yet."
        top_recommendation = user_recommendations[0] if user_recommendations else "No clear recommendation trend yet."
        return (
            f"Based on {analyzed_count} analyzed videos, creator sentiment trends {overall_sentiment} with "
            f"{risk_level} risk pressure. The strongest positive signal is: {top_praise} "
            f"The most repeated concern is: {top_criticism} "
            f"Creators most often recommend: {top_recommendation}"
        )

    @staticmethod
    def _build_markdown_report(
        *,
        generated_at: datetime,
        analyzed_video_count: int,
        total_video_count: int,
        coverage_pct: float,
        payload: Dict[str, object],
        excluded_reasons: List[str],
    ) -> str:
        generated_text = generated_at.strftime("%Y-%m-%d %H:%M UTC")
        praise_points = payload.get("praise_points", [])
        criticism_points = payload.get("criticism_points", [])
        user_recommendations = payload.get("user_recommendations", [])
        excluded_text = ", ".join(excluded_reasons) if excluded_reasons else "none"
        praise_lines = [f"- {item}" for item in praise_points] if praise_points else ["- No recurring praise yet."]
        criticism_lines = [f"- {item}" for item in criticism_points] if criticism_points else ["- No recurring criticism yet."]
        recommendation_lines = (
            [f"- {item}" for item in user_recommendations] if user_recommendations else ["- No recurring recommendation yet."]
        )

        lines = [
            "# Project Insights Report",
            "",
            f"- Generated at: {generated_text}",
            f"- Analyzed videos: {analyzed_video_count}",
            f"- Total project videos: {total_video_count}",
            f"- Coverage: {coverage_pct}%",
            f"- Excluded reasons: {excluded_text}",
            "",
            "## Executive Dashboard",
            f"- Overall sentiment: {payload.get('overall_sentiment', 'neutral')}",
            f"- Risk level: {payload.get('risk_level', 'low')}",
            f"- Risk score: {payload.get('risk_score', 0.0)} / 10",
            (
                "- Sentiment distribution: "
                f"positive {payload.get('sentiment_breakdown', {}).get('positive', 0)}, "
                f"neutral {payload.get('sentiment_breakdown', {}).get('neutral', 0)}, "
                f"negative {payload.get('sentiment_breakdown', {}).get('negative', 0)}"
            ),
            (
                "- Risk distribution: "
                f"low {payload.get('risk_breakdown', {}).get('low', 0)}, "
                f"medium {payload.get('risk_breakdown', {}).get('medium', 0)}, "
                f"high {payload.get('risk_breakdown', {}).get('high', 0)}, "
                f"critical {payload.get('risk_breakdown', {}).get('critical', 0)}"
            ),
            (
                "- Reach-weighted impact: "
                f"negative reach share {payload.get('reach_metrics', {}).get('negative_reach_share_pct', 0.0)}%, "
                f"critical risk reach {payload.get('reach_metrics', {}).get('critical_risk_reach', 0)} views"
            ),
            "",
            "## Praise",
            *praise_lines,
            "",
            "## Criticism",
            *criticism_lines,
            "",
            "## User Recommendations",
            *recommendation_lines,
            "",
            "## Team Action Plan",
            f"- Product: Address top criticism -> {criticism_points[0] if criticism_points else 'No recurring technical criticism yet.'}",
            f"- Product Marketing: Amplify top proof point -> {praise_points[0] if praise_points else 'No recurring praise signal yet.'}",
            f"- Marketing: Prioritize creator follow-up using top recommendation -> {user_recommendations[0] if user_recommendations else 'No recurring recommendation yet.'}",
            "",
            "## Summary",
            f"- Headline: {payload.get('summary_headline', '')}",
            f"- Core insight: {payload.get('summary_body', '')}",
            f"- Top risk trigger: {payload.get('top_risk_trigger', '')}",
        ]
        return "\n".join(lines)

    @staticmethod
    def _empty_payload(*, total_video_count: int) -> Dict[str, object]:
        return {
            "overall_sentiment": "neutral",
            "risk_level": "low",
            "risk_score": 0.0,
            "summary_headline": "No analyzed videos yet for this project.",
            "summary_body": (
                f"The project currently has {total_video_count} videos but none with completed analysis and stored"
                " transcript data, so insights cannot be generated yet."
            ),
            "top_risk_trigger": "No trigger available until at least one video is analyzed.",
            "praise_points": [],
            "criticism_points": [],
            "user_recommendations": [],
        }
