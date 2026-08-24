"""Health-check route."""

from fastapi import APIRouter

from ..models.code_request import HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Report that the API process is ready to receive requests."""

    return HealthResponse(status="ok")

