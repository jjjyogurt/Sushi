from app.config import get_settings
from app.services.gemini_client import GeminiClient


class GeminiHealthService:
    def __init__(self):
        self.client = GeminiClient(get_settings())

    def status(self, *, probe: bool = False) -> dict:
        return self.client.health_status(probe=probe)
