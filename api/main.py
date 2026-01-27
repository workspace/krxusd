from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.core.config import settings
from api.core.database import close_db, init_db
from api.core.redis import close_redis, init_redis
from api.routers import api_router
from api.services.scheduler_service import init_scheduler, shutdown_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup
    await init_db()
    await init_redis()

    # Initialize scheduler
    if settings.scheduler_enabled:
        await init_scheduler()
        logger.info("Realtime data scheduler initialized")

    yield

    # Shutdown
    if settings.scheduler_enabled:
        await shutdown_scheduler()
        logger.info("Realtime data scheduler shut down")

    await close_db()
    await close_redis()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="KRX Stock Prices in USD - API Service",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "api": settings.api_v1_prefix,
    }
