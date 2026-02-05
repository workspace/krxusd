"""KRXUSD API - KRW 주가를 USD로 환산하여 보여주는 서비스."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import exchange_router, stocks_router, health_router

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="""
# KRXUSD API

한국 주식의 USD 환산 가격을 제공하는 API입니다.

## 핵심 기능

**USD 환산 주가** = KRW 주가 / 당일 USD/KRW 환율 종가

투자자가 한국 주식의 실제 달러 가치 변동을 직관적으로 파악할 수 있게 합니다.

## API 카테고리

- **Exchange Rate**: USD/KRW 환율 조회
- **Stocks**: 주식 검색, 정보, 가격 히스토리
- **USD Conversion**: KRW → USD 환산 가격 (핵심!)

## Mock Mode

현재 Mock 모드: **{mock_mode}**

Mock 모드에서는 실제 API 호출 없이 가짜 데이터를 반환합니다.
프론트엔드 개발 시 API 키 없이도 개발이 가능합니다.
""".format(mock_mode="ON" if settings.use_mock else "OFF"),
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health_router)
app.include_router(exchange_router)
app.include_router(stocks_router)


@app.get("/")
def root():
    """Root endpoint - API 정보."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "mock_mode": settings.use_mock,
        "docs": "/docs",
        "description": "KRW 주가를 USD로 환산하여 보여주는 서비스",
    }
