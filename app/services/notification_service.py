from app.models.enums import RiskLevel


class NotificationService:
    def build_alert_message(self, *, title: str, severity: RiskLevel, summary: str) -> str:
        return (
            f"[{severity.value.upper()}] Influencer content requires attention: {title}. "
            f"Summary: {summary[:300]}"
        )

