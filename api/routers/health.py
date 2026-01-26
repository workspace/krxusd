from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.redis import get_redis
from api.schemas.common import APIResponse

router = APIRouter()


@router.get("/health")
async def health_check() -> APIResponse[dict]:
    """Basic health check endpoint"""
    return APIResponse(
        data={"status": "healthy", "service": "krxusd-api"}
    )


@router.get("/health/ready")
async def readiness_check(
    db: AsyncSession = Depends(get_db),
) -> APIResponse[dict]:
    """
    Readiness check - verifies database and Redis connectivity
    """
    checks = {
        "database": False,
        "redis": False,
    }

    # Check database
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        pass

    # Check Redis
    try:
        redis = await get_redis()
        await redis.ping()
        checks["redis"] = True
    except Exception:
        pass

    all_ready = all(checks.values())

    return APIResponse(
        success=all_ready,
        message="Ready" if all_ready else "Not ready",
        data=checks,
    )
