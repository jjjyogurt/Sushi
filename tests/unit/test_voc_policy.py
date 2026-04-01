import pytest

import app.models  # noqa: F401
from app.services.voc_policy import classify_confidence, evaluate_publish_gate
from app.services.voc_service import VocService


def test_publish_gate_thresholds():
    gate = evaluate_publish_gate(total_rows=100, failed_rows=1, has_critical_failure=False)
    assert gate.allowed is True
    assert gate.requires_acknowledgment is False

    gate = evaluate_publish_gate(total_rows=100, failed_rows=2, has_critical_failure=False)
    assert gate.allowed is True
    assert gate.requires_acknowledgment is True

    gate = evaluate_publish_gate(total_rows=100, failed_rows=6, has_critical_failure=False)
    assert gate.allowed is False


def test_publish_gate_blocks_on_critical_failure():
    gate = evaluate_publish_gate(total_rows=100, failed_rows=0, has_critical_failure=True)
    assert gate.allowed is False
    assert gate.requires_acknowledgment is False


def test_confidence_classification():
    assert classify_confidence(0.8) == "high"
    assert classify_confidence(0.79) == "medium"
    assert classify_confidence(0.6) == "medium"
    assert classify_confidence(0.59) == "low"


def test_skill_activation_requires_validation(db_session):
    service = VocService(db_session)
    version = service.create_skill_version("cleaner", "Draft", "content")
    with pytest.raises(ValueError):
        service.activate_skill_version(version.id)


def test_template_activation_requires_preview(db_session):
    service = VocService(db_session)
    template = service.create_template("Template", "content")
    with pytest.raises(ValueError):
        service.activate_template(template.id)
