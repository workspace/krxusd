"""Health check router."""
from fastapi import APIRouter

from app.config import settings

router = APIRouter(prefix="/api/health", tags=["Health"])


@router.get("")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "mock_mode": settings.use_mock,
    }
