"""
Scheduler Router

실시간 데이터 업데이트 스케줄러 관리 API 엔드포인트
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Any

from api.core.market_hours import get_market_status_dict
from api.services.scheduler_service import (
    get_scheduler_status,
    trigger_manual_update,
    register_active_symbol,
    unregister_active_symbol,
    get_active_symbols,
)

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


class SymbolRequest(BaseModel):
    """종목 등록/해제 요청"""
    symbol: str = Field(..., description="종목 코드", min_length=1, max_length=20)


class SymbolResponse(BaseModel):
    """종목 등록/해제 응답"""
    symbol: str
    registered: bool
    message: str


class SchedulerStatusResponse(BaseModel):
    """스케줄러 상태 응답"""
    enabled: bool
    running: bool
    jobs: list[dict[str, Any]] | None = None
    state: dict[str, Any] | None = None
    recent_history: list[dict[str, Any]] | None = None
    active_symbols_count: int
    market_status: str
    is_trading_time: bool
    config: dict[str, Any] | None = None


class ActiveSymbolsResponse(BaseModel):
    """활성 종목 목록 응답"""
    count: int
    symbols: list[str]


class MarketStatusResponse(BaseModel):
    """시장 상태 응답"""
    status: str
    is_trading_time: bool
    current_time_kst: str
    market_open_at: str | None
    market_close_at: str | None
    next_open_at: str | None
    message: str


class ManualUpdateResponse(BaseModel):
    """수동 업데이트 응답"""
    triggered: bool
    timestamp: str


@router.get(
    "/status",
    response_model=SchedulerStatusResponse,
    summary="스케줄러 상태 조회",
    description="실시간 데이터 업데이트 스케줄러의 현재 상태를 조회합니다.",
)
async def get_status() -> SchedulerStatusResponse:
    """
    스케줄러 상태 조회

    - 스케줄러 실행 상태
    - 등록된 작업 목록
    - 최근 실행 기록
    - 활성 종목 수
    - 시장 상태
    """
    status_data = await get_scheduler_status()
    return SchedulerStatusResponse(**status_data)


@router.get(
    "/market-status",
    response_model=MarketStatusResponse,
    summary="시장 운영 상태 조회",
    description="KRX 시장의 현재 운영 상태를 조회합니다.",
)
async def get_market_status_endpoint() -> MarketStatusResponse:
    """
    시장 상태 조회

    - 현재 시장 상태 (장전/장중/장후/휴장)
    - 실시간 업데이트 가능 여부
    - 장 시작/종료 시간
    """
    market_data = get_market_status_dict()
    return MarketStatusResponse(**market_data)


@router.post(
    "/trigger",
    response_model=ManualUpdateResponse,
    summary="수동 업데이트 트리거",
    description="실시간 업데이트를 수동으로 트리거합니다.",
)
async def trigger_update() -> ManualUpdateResponse:
    """
    수동 업데이트 트리거

    테스트 또는 긴급 상황에서 즉시 업데이트를 실행합니다.
    """
    result = await trigger_manual_update()
    return ManualUpdateResponse(**result)


@router.post(
    "/symbols/register",
    response_model=SymbolResponse,
    summary="활성 종목 등록",
    description="종목을 실시간 업데이트 대상으로 등록합니다.",
)
async def register_symbol(request: SymbolRequest) -> SymbolResponse:
    """
    활성 종목 등록

    사용자가 종목 상세 페이지를 조회할 때 호출됩니다.
    등록된 종목은 1분마다 자동으로 가격이 업데이트됩니다.

    종목은 마지막 조회 후 3분이 지나면 자동으로 비활성화됩니다.
    """
    symbol = request.symbol.upper()
    await register_active_symbol(symbol)

    return SymbolResponse(
        symbol=symbol,
        registered=True,
        message=f"Symbol {symbol} registered for realtime updates",
    )


@router.post(
    "/symbols/unregister",
    response_model=SymbolResponse,
    summary="활성 종목 해제",
    description="종목을 실시간 업데이트 대상에서 제거합니다.",
)
async def unregister_symbol(request: SymbolRequest) -> SymbolResponse:
    """
    활성 종목 해제

    사용자가 종목 상세 페이지를 떠날 때 호출할 수 있습니다.
    (선택사항 - 등록된 종목은 3분 후 자동으로 만료됩니다)
    """
    symbol = request.symbol.upper()
    await unregister_active_symbol(symbol)

    return SymbolResponse(
        symbol=symbol,
        registered=False,
        message=f"Symbol {symbol} unregistered from realtime updates",
    )


@router.post(
    "/symbols/refresh",
    response_model=SymbolResponse,
    summary="활성 종목 갱신",
    description="종목의 활성 상태를 갱신합니다 (heartbeat).",
)
async def refresh_symbol(request: SymbolRequest) -> SymbolResponse:
    """
    활성 종목 갱신 (Heartbeat)

    사용자가 종목 페이지에 계속 머물러 있을 때 주기적으로 호출합니다.
    이를 통해 종목이 활성 상태로 유지됩니다.
    """
    symbol = request.symbol.upper()
    await register_active_symbol(symbol)  # 같은 동작

    return SymbolResponse(
        symbol=symbol,
        registered=True,
        message=f"Symbol {symbol} refreshed",
    )


@router.get(
    "/symbols/active",
    response_model=ActiveSymbolsResponse,
    summary="활성 종목 목록 조회",
    description="현재 실시간 업데이트 대상인 종목 목록을 조회합니다.",
)
async def get_active_symbols_list() -> ActiveSymbolsResponse:
    """
    활성 종목 목록 조회

    현재 사용자들이 조회 중인 종목 목록을 반환합니다.
    """
    symbols = await get_active_symbols()

    return ActiveSymbolsResponse(
        count=len(symbols),
        symbols=symbols,
    )
