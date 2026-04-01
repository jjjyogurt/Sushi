from dataclasses import dataclass

from app.config import get_settings


@dataclass(frozen=True)
class PublishGateResult:
    allowed: bool
    requires_acknowledgment: bool
    reason: str


def evaluate_publish_gate(total_rows: int, failed_rows: int, has_critical_failure: bool) -> PublishGateResult:
    settings = get_settings()
    if total_rows <= 0:
        return PublishGateResult(False, False, "No rows available for publishing.")
    if has_critical_failure:
        return PublishGateResult(False, False, "Critical source failure blocks publishing.")

    ratio = failed_rows / total_rows
    if ratio <= settings.voc_failed_ratio_warn:
        return PublishGateResult(True, False, "Publish allowed with warning.")
    if ratio <= settings.voc_failed_ratio_ack:
        return PublishGateResult(True, True, "Publish requires reviewer acknowledgment.")
    return PublishGateResult(False, False, "Failed-row ratio exceeds publish threshold.")


def classify_confidence(value: float) -> str:
    settings = get_settings()
    if value >= settings.voc_confidence_high:
        return "high"
    if value >= settings.voc_confidence_medium:
        return "medium"
    return "low"


def requires_manual_approval(confidence_value: float) -> bool:
    return classify_confidence(confidence_value) == "low"
