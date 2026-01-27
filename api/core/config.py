from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Application
    app_name: str = "KRXUSD API"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: str = "development"

    # Database
    database_url: str = "postgresql+asyncpg://krxusd:krxusd@localhost:5432/krxusd"

    # Redis
    redis_url: str = "redis://localhost:6379"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000"]

    # API Settings
    api_v1_prefix: str = "/api/v1"

    # Scheduler Settings
    scheduler_enabled: bool = True
    scheduler_realtime_interval_seconds: int = 60  # 1분 단위 업데이트
    scheduler_popular_stocks_interval_seconds: int = 300  # 5분 단위 인기 종목 업데이트
    scheduler_max_batch_size: int = 20  # 한 번에 업데이트할 최대 종목 수
    scheduler_active_symbol_ttl_seconds: int = 180  # 조회 중인 종목 TTL (3분)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
