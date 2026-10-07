from fastapi import APIRouter

from backend.models.health_model import HealthResponse
from backend.services.health_service import HealthService

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthService().get_status()


@router.get("/")
def root() -> dict[str, str]:
    return {"service": "motor-decision", "docs": "/docs", "health": "/health"}
