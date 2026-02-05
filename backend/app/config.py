"""Application configuration with Mock mode support."""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # API Settings
    app_name: str = "KRXUSD API"
    app_version: str = "1.0.0"
    debug: bool = True
    
    # Mock Mode - 프론트엔드 개발용
    # API 키가 필요한 외부 API는 Mock 모드에서 가짜 데이터 반환
    use_mock: bool = True
    
    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    
    # Database (선택)
    database_url: str = "sqlite:///./krxusd.db"
    
    # Redis (선택)
    redis_url: str = "redis://localhost:6379"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
