from app.models.analysis_result import AnalysisResult
from app.models.chat import ChatMessage
from app.models.incident import Alert, Incident
from app.models.monitor_profile import MonitorProfile
from app.schemas.analysis import AnalysisResponse
from app.schemas.chat import ChatMessageResponse
from app.schemas.incident import AlertResponse, IncidentResponse
from app.schemas.monitor import MonitorProfileResponse
from app.schemas.video import VideoResponse
from app.utils.json_codec import decode_json


def map_monitor_response(model: MonitorProfile) -> MonitorProfileResponse:
    return MonitorProfileResponse(
        id=model.id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        name=model.name,
        brand_keywords=decode_json(model.brand_keywords, []),
        markets=decode_json(model.markets, []),
        languages=decode_json(model.languages, []),
        alert_sensitivity=model.alert_sensitivity,
        is_active=model.is_active,
    )


def map_video_response(model, *, monitor_profile_name=None, sentiment_label=None) -> VideoResponse:
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
    )


def map_analysis_response(model: AnalysisResult) -> AnalysisResponse:
    return AnalysisResponse(
        id=model.id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        video_candidate_id=model.video_candidate_id,
        analysis_version=model.analysis_version,
        model_name=model.model_name,
        status=model.status,
        transcript_text=model.transcript_text,
        summary_text=model.summary_text,
        translated_summary=model.translated_summary,
        sentiment=model.sentiment,
        risk_level=model.risk_level,
        confidence_score=float(model.confidence_score or "0"),
        evidence=decode_json(model.evidence_json, []),
        insights=decode_json(model.insights_json, []),
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
    return AlertResponse(
        id=model.id,
        created_at=model.created_at,
        updated_at=model.updated_at,
        incident_id=model.incident_id,
        channel=model.channel,
        message=model.message,
        is_sent=model.is_sent,
    )

