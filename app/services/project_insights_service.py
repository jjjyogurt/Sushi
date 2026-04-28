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

    def get_current_report(self, monitor_profile_id: int) -> Optional[ProjectInsightReport]:
        self._require_profile(monitor_profile_id)
        return self.repository.get_latest_for_profile(monitor_profile_id)

    def list_report_history(self, monitor_profile_id: int, *, limit: int = 20) -> List[ProjectInsightReport]:
        self._require_profile(monitor_profile_id)
        return self.repository.list_for_profile(monitor_profile_id, limit=limit)

    def refresh_report(self, monitor_profile_id: int) -> ProjectInsightReport:
        profile = self._require_profile(monitor_profile_id)
        video_analysis_pairs = self.repository.list_videos_with_latest_analysis(
            monitor_profile_id=monitor_profile_id,
            language="en",
        )

        total_video_count = len(video_analysis_pairs)
        completed_results = []
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

        analyzed_video_count = len(completed_results)
        excluded_video_count = max(0, total_video_count - analyzed_video_count)
        coverage_pct = round((analyzed_video_count / total_video_count) * 100, 1) if total_video_count > 0 else 0.0
        excluded_reasons = [
            f"{reason}:{count}" for reason, count in excluded_reason_counter.most_common() if count > 0
        ]

        if analyzed_video_count == 0:
            payload = self._empty_payload(total_video_count=total_video_count)
        else:
            fallback_payload = self._build_payload(completed_results)
            payload = self._build_payload_with_gemini(
                profile_name=str(profile.name or "").strip() or f"Project {monitor_profile_id}",
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
            business_impact=payload["business_impact"],
            praise_points_json=encode_json(payload["praise_points"]),
            criticism_points_json=encode_json(payload["criticism_points"]),
            user_recommendations_json=encode_json(payload["user_recommendations"]),
            excluded_reasons_json=encode_json(excluded_reasons),
            report_markdown=report_markdown,
        )

    def _build_payload_with_gemini(
        self,
        *,
        profile_name: str,
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
            "business_impact": generated.get("business_impact") or fallback_payload.get("business_impact", ""),
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

    def _build_payload(self, completed_results) -> Dict[str, object]:
        sentiment_counter: Counter[str] = Counter()
        praise_counter: Counter[str] = Counter()
        criticism_counter: Counter[str] = Counter()
        recommendation_counter: Counter[str] = Counter()
        headline_samples: List[str] = []

        risk_total = 0.0
        for result in completed_results:
            sentiment_value = getattr(result.sentiment, "value", str(result.sentiment or "neutral")).lower()
            risk_value = getattr(result.risk_level, "value", str(result.risk_level or "low")).lower()
            sentiment_counter[sentiment_value] += 1
            risk_total += self.RISK_SCORE_BY_LEVEL.get(risk_value, 5.0)

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

        analyzed_count = len(completed_results)
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
        business_impact = self._build_business_impact(risk_level=risk_level, analyzed_count=analyzed_count)

        return {
            "overall_sentiment": overall_sentiment,
            "risk_level": risk_level,
            "risk_score": average_risk_score,
            "summary_headline": summary_headline,
            "summary_body": summary_body,
            "business_impact": business_impact,
            "praise_points": praise_points,
            "criticism_points": criticism_points,
            "user_recommendations": user_recommendations,
        }

    @staticmethod
    def _build_gemini_records(completed_results) -> List[dict]:
        max_videos = 80
        max_transcript_chars_per_video = 4000
        max_total_transcript_chars = 180000
        total_chars = 0
        records: List[dict] = []

        for result in completed_results[:max_videos]:
            transcript = str(result.transcript_text or "").strip()
            transcript_excerpt = transcript[:max_transcript_chars_per_video]
            next_total = total_chars + len(transcript_excerpt)
            if next_total > max_total_transcript_chars:
                break

            insights_payload = decode_json(result.insights_json, {})
            parsed = ProjectInsightsService._parse_insights_payload(insights_payload)
            evidence = decode_json(result.evidence_json, [])
            record = {
                "video_id": int(result.video_candidate_id),
                "summary_headline": str(result.summary_headline or "").strip(),
                "summary_body": str(result.summary_body or "").strip(),
                "business_impact": str(result.business_impact or "").strip(),
                "sentiment": getattr(result.sentiment, "value", str(result.sentiment or "neutral")).lower(),
                "risk_level": getattr(result.risk_level, "value", str(result.risk_level or "medium")).lower(),
                "praise_points": parsed["praise_points"],
                "criticism_points": parsed["criticism_points"],
                "action_recommendation": parsed["user_recommendations"][0] if parsed["user_recommendations"] else "",
                "evidence": evidence if isinstance(evidence, list) else [],
                "transcript_excerpt": transcript_excerpt,
                "transcript_truncated": len(transcript_excerpt) < len(transcript),
            }
            records = [*records, record]
            total_chars = next_total
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
    def _build_business_impact(*, risk_level: str, analyzed_count: int) -> str:
        if risk_level in {"high", "critical"}:
            return (
                f"High-severity issues across {analyzed_count} analyzed videos can reduce conversion and increase"
                " PR risk if not addressed quickly."
            )
        if risk_level == "medium":
            return (
                f"Mixed sentiment across {analyzed_count} analyzed videos may slow growth unless messaging and product"
                " fixes are aligned."
            )
        return (
            f"Current signals across {analyzed_count} analyzed videos are mostly stable; amplify strengths while"
            " monitoring for emerging risks."
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
            "## Sentiment & Risk",
            f"- Overall sentiment: {payload.get('overall_sentiment', 'neutral')}",
            f"- Risk level: {payload.get('risk_level', 'low')}",
            f"- Risk score: {payload.get('risk_score', 0.0)} / 10",
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
            "## Methodology",
            "- Source scope: latest completed video analyses in this project only.",
            "- Inclusion criteria: completed analysis with transcript stored in DB.",
            "- Transcript policy: no external transcript API calls during insights generation.",
            f"- Coverage note: {analyzed_video_count}/{total_video_count} videos included.",
            "",
            "## Summary",
            f"- Headline: {payload.get('summary_headline', '')}",
            f"- Body: {payload.get('summary_body', '')}",
            f"- Business impact: {payload.get('business_impact', '')}",
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
            "business_impact": "Run analysis on project videos to unlock reliable sentiment and risk signals.",
            "praise_points": [],
            "criticism_points": [],
            "user_recommendations": [],
        }
