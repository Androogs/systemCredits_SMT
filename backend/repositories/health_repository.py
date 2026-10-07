from backend.config import get_settings
from backend.models.health_model import HealthResponse


class HealthRepository:
    def get_status(self) -> HealthResponse:
        settings = get_settings()
        return HealthResponse(status="ok", environment=settings.environment, version=settings.version)
