from datetime import datetime, timezone

from app.api.mappers import map_analysis_response
from app.models.analysis_result import AnalysisResult
from app.models.enums import AnalysisStatus, RiskLevel, Sentiment
from app.utils.json_codec import encode_json


def _build_analysis_model():
    now = datetime.now(timezone.utc)
    model = AnalysisResult(
        video_candidate_id=1,
        analysis_version="unit-v1",
        language="en",
        model_name="gemini-test",
        status=AnalysisStatus.COMPLETED,
        transcript_text="00:01 hello",
        summary_text="summary",
        translated_summary="summary",
        summary_headline="headline",
        summary_body="body",
        sentiment=Sentiment.NEUTRAL,
        risk_level=RiskLevel.LOW,
        confidence_score="0.75",
        evidence_json=encode_json([]),
        insights_json=encode_json({}),
        error_message="",
    )
    model.id = 101
    model.created_at = now
    model.updated_at = now
    model.comment_summary_text = ""
    return model


def test_map_analysis_response_supports_structured_comment_points():
    model = _build_analysis_model()
    model.comment_summary_text = "comment summary"
    model.comment_highlights_json = encode_json([{"point": "Great battery", "quote": "battery is awesome"}])
    model.comment_lowlights_json = encode_json([{"point": "Price concern", "quote": "too expensive"}])

    response = map_analysis_response(model)

    assert response.comment_summary_text == "comment summary"
    assert response.comment_highlights[0].point == "Great battery"
    assert response.comment_highlights[0].quote == "battery is awesome"
    assert response.comment_lowlights[0].point == "Price concern"
    assert response.comment_lowlights[0].quote == "too expensive"


def test_map_analysis_response_keeps_backward_compatibility_for_string_points():
    model = _build_analysis_model()
    model.comment_highlights_json = encode_json(["Great value"])
    model.comment_lowlights_json = encode_json(["App crashes"])

    response = map_analysis_response(model)

    assert response.comment_highlights[0].point == "Great value"
    assert response.comment_highlights[0].quote == ""
    assert response.comment_lowlights[0].point == "App crashes"
    assert response.comment_lowlights[0].quote == ""
