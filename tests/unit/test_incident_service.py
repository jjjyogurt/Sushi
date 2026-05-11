from app.models.analysis_result import AnalysisResult
from app.models.enums import AnalysisStatus, QueueState, RiskLevel, Sentiment
from app.services.incident_service import IncidentService
from app.utils.json_codec import encode_json


def _seed_analysis(db_session, video_id: int, risk_level: RiskLevel):
    analysis = AnalysisResult(
        video_candidate_id=video_id,
        analysis_version="v1",
        model_name="gemini-3",
        status=AnalysisStatus.COMPLETED,
        transcript_text="seed",
        summary_text="seed summary",
        translated_summary="seed summary",
        sentiment=Sentiment.NEUTRAL,
        risk_level=risk_level,
        confidence_score="0.8",
        evidence_json=encode_json([{"timestamp": "00:10", "quote": "seed", "reason": "seed"}]),
        insights_json=encode_json(["seed"]),
    )
    db_session.add(analysis)
    db_session.commit()
    db_session.refresh(analysis)
    return analysis


def test_escalation_creates_alert_for_medium_or_high(db_session, discovered_video):
    discovered_video.queue_state = QueueState.APPROVED
    db_session.commit()
    _seed_analysis(db_session, discovered_video.id, RiskLevel.HIGH)

    service = IncidentService(db_session)
    result = service.escalate(video_id=discovered_video.id, owner="owner-a", notes="watch")
    alerts = service.list_alerts()

    assert result.incident.severity == RiskLevel.HIGH
    assert result.alert_created is True
    assert len(alerts) == 1
    assert "requires attention" in alerts[0].message


def test_escalation_low_risk_creates_incident_without_alert(db_session, discovered_video):
    discovered_video.queue_state = QueueState.APPROVED
    db_session.commit()
    _seed_analysis(db_session, discovered_video.id, RiskLevel.LOW)

    service = IncidentService(db_session)
    result = service.escalate(video_id=discovered_video.id, owner="owner-a", notes="watch")
    alerts = service.list_alerts()

    assert result.incident.severity == RiskLevel.LOW
    assert result.alert_created is False
    assert len(alerts) == 0


def test_escalation_without_analysis_raises_error(db_session, discovered_video):
    service = IncidentService(db_session)
    try:
        service.escalate(video_id=discovered_video.id, owner="owner-a", notes="watch")
    except ValueError as error:
        assert "without completed analysis" in str(error).lower()
    else:
        raise AssertionError("Expected ValueError when escalating without analysis.")
