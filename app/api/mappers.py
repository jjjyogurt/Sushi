from app.models.analysis_result import AnalysisResult
from app.models.analysis_batch import AnalysisBatch, AnalysisBatchItem
from app.models.chat import ChatMessage
from app.models.enums import RiskLevel
from app.models.incident import Alert, Incident
from app.models.monitor_profile import MonitorProfile
from app.schemas.analysis import AnalysisResponse
from app.schemas.analysis_batch import AnalysisBatchItemResponse, AnalysisBatchResponse
from app.schemas.chat import ChatMessageResponse
from app.schemas.incident import AlertResponse, IncidentResponse
from app.schemas.monitor import MonitorProfileResponse
from app.schemas.video import VideoResponse
from app.utils.json_codec import decode_json


def normalize_comment_points(raw_points):
    if not isinstance(raw_points, list):
        return []
    normalized = []
    for item in raw_points:
        if isinstance(item, dict):
            point = str(item.get("point", "")).strip()
            quote = str(item.get("quote", "")).strip()
            if not point and quote:
                point = quote
            if not point:
                continue
            normalized = [*normalized, {"point": point, "quote": quote}]
            continue
        point_text = str(item).strip()
        if point_text:
            normalized = [*normalized, {"point": point_text, "quote": ""}]
    return normalized[:3]


def normalize_audience_profiles(raw_profiles):
    if not isinstance(raw_profiles, list):
        return []
    normalized = []
    for item in raw_profiles:
        if not isinstance(item, dict):
            continue
        profile_type = str(item.get("type") or "").strip()
        description = str(item.get("description") or "").strip()
        if profile_type and description:
            normalized = [*normalized, {"type": profile_type, "description": description}]
    return normalized[:3]


def normalize_usage_scenarios(raw_scenarios):
    if not isinstance(raw_scenarios, list):
        return []
    cleaned = [item for item in [str(raw).strip() for raw in raw_scenarios] if item]
    return cleaned[:4]


def map_monitor_response(model: MonitorProfile) -> MonitorProfileResponse:
    return MonitorProfileResponse(
        id=model.id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        name=model.name,
        brand_keywords=decode_json(model.brand_keywords, []),
        markets=decode_json(model.markets, []),
        languages=decode_json(model.languages, []),
        key_products=decode_json(model.key_products, []),
        alert_sensitivity=model.alert_sensitivity,
        is_active=model.is_active,
    )


def map_video_response(
    model,
    *,
    monitor_profile_name=None,
    sentiment_label=None,
    latest_analysis_status=None,
    is_bookmarked: bool = False,
) -> VideoResponse:
    return VideoResponse(
        id=model.id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        monitor_profile_id=model.monitor_profile_id,
        monitor_profile_name=monitor_profile_name,
        youtube_video_id=model.youtube_video_id,
        video_url=model.video_url,
        title=model.title,
        channel_name=model.channel_name,
        language=model.language,
        published_at=model.published_at,
        relevance_score=model.relevance_score,
        relevance_reason=model.relevance_reason,
        queue_state=model.queue_state,
        sentiment_label=sentiment_label,
        latest_analysis_status=latest_analysis_status,
        is_bookmarked=is_bookmarked,
        assigned_user_id=(model.assigned_user_id or None),
    )


def map_analysis_response(model: AnalysisResult) -> AnalysisResponse:
    raw_insights_payload = decode_json(model.insights_json, [])
    if isinstance(raw_insights_payload, dict):
        raw_insights = raw_insights_payload.get("insights", [])
        raw_praise_points = raw_insights_payload.get("praise_points", [])
        raw_criticism_points = raw_insights_payload.get("criticism_points", [])
        raw_audience_profiles = raw_insights_payload.get("audience_profiles", [])
        raw_usage_scenarios = raw_insights_payload.get("usage_scenarios", [])
        insights = [item for item in [str(value).strip() for value in raw_insights] if item] if isinstance(raw_insights, list) else []
        praise_points = (
            [item for item in [str(value).strip() for value in raw_praise_points] if item][:5]
            if isinstance(raw_praise_points, list)
            else []
        )
        criticism_points = (
            [item for item in [str(value).strip() for value in raw_criticism_points] if item][:5]
            if isinstance(raw_criticism_points, list)
            else []
        )
        audience_profiles = normalize_audience_profiles(raw_audience_profiles)
        usage_scenarios = normalize_usage_scenarios(raw_usage_scenarios)
        action_recommendation = str(raw_insights_payload.get("action_recommendation", "")).strip()
    else:
        insights = (
            [item for item in [str(value).strip() for value in raw_insights_payload] if item]
            if isinstance(raw_insights_payload, list)
            else []
        )
        praise_points = []
        criticism_points = []
        audience_profiles = []
        usage_scenarios = []
        action_recommendation = ""

    raw_comment_highlights = decode_json(model.comment_highlights_json, [])
    raw_comment_lowlights = decode_json(model.comment_lowlights_json, [])
    comment_highlights = normalize_comment_points(raw_comment_highlights)
    comment_lowlights = normalize_comment_points(raw_comment_lowlights)

    return AnalysisResponse(
        id=model.id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        video_candidate_id=model.video_candidate_id,
        analysis_version=model.analysis_version,
        language=model.language,
        model_name=model.model_name,
        status=model.status,
        transcript_text=model.transcript_text,
        summary_text=model.summary_text,
        translated_summary=model.translated_summary,
        summary_headline=model.summary_headline,
        summary_body=model.summary_body,
        comment_summary_text=model.comment_summary_text,
        comment_highlights=comment_highlights,
        comment_lowlights=comment_lowlights,
        sentiment=model.sentiment,
        risk_level=model.risk_level,
        confidence_score=float(model.confidence_score or "0"),
        evidence=decode_json(model.evidence_json, []),
        insights=insights,
        praise_points=praise_points,
        criticism_points=criticism_points,
        audience_profiles=audience_profiles,
        usage_scenarios=usage_scenarios,
        action_recommendation=action_recommendation,
        error_message=model.error_message,
    )


def map_chat_message_response(model: ChatMessage) -> ChatMessageResponse:
    return ChatMessageResponse(
        id=model.id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        role=model.role,
        content=model.content,
        citations=decode_json(model.citations_json, []),
        confidence_score=float(model.confidence_score or "0"),
        insufficient_evidence=model.insufficient_evidence,
    )


def map_analysis_batch_response(model: AnalysisBatch) -> AnalysisBatchResponse:
    return AnalysisBatchResponse(
        id=model.id,
        monitor_profile_id=model.monitor_profile_id,
        created_by=model.created_by,
        status=model.status,
        total_count=model.total_count,
        processed_count=model.processed_count,
        success_count=model.success_count,
        failed_count=model.failed_count,
        last_error=model.last_error,
        started_at=model.started_at,
        finished_at=model.finished_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def map_analysis_batch_item_response(model: AnalysisBatchItem) -> AnalysisBatchItemResponse:
    return AnalysisBatchItemResponse(
        id=model.id,
        batch_id=model.batch_id,
        video_id=model.video_id,
        status=model.status,
        attempt_count=model.attempt_count,
        error_message=model.error_message,
        started_at=model.started_at,
        finished_at=model.finished_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def map_incident_response(model: Incident) -> IncidentResponse:
    return IncidentResponse(
        id=model.id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        video_candidate_id=model.video_candidate_id,
        severity=model.severity,
        status=model.status,
        owner=model.owner,
        notes=model.notes,
    )


def map_alert_response(model: Alert) -> AlertResponse:
    incident = model.incident
    video = incident.video_candidate if incident else None
    return AlertResponse(
        id=model.id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        incident_id=model.incident_id,
        video_candidate_id=incident.video_candidate_id if incident else 0,
        video_title=video.title if video else "",
        severity=incident.severity if incident else RiskLevel.LOW,
        owner=incident.owner if incident else "",
        channel=model.channel,
        message=model.message,
        is_sent=model.is_sent,
    )
