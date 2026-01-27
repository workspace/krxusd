"""
Scheduler Router

실시간 데이터 업데이트 스케줄러 관리 API 엔드포인트
- 실시간 업데이트 (1분 간격)
- 일일 배치 업데이트 (장 마감 후 16:00)
"""

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Any

from api.core.market_hours import get_market_status_dict
from api.services.scheduler_service import (
    get_scheduler_status,
    trigger_manual_update,
    register_active_symbol,
    unregister_active_symbol,
    get_active_symbols,
    trigger_daily_batch_update,
    get_batch_update_status,
    get_popular_stocks_for_batch,
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


class BatchUpdateStatusResponse(BaseModel):
    """배치 업데이트 상태 응답"""
    state: dict[str, Any] | None
    recent_history: list[dict[str, Any]] | None
    next_run_at: str | None
    config: dict[str, Any]


class BatchUpdateTriggerResponse(BaseModel):
    """배치 업데이트 트리거 응답"""
    triggered: bool
    message: str


class BatchUpdateResultResponse(BaseModel):
    """배치 업데이트 결과 응답"""
    success: bool
    date: str | None = None
    duration_ms: int | None = None
    total_stocks: int | None = None
    updated_count: int | None = None
    failed_count: int | None = None
    skipped: bool | None = None
    reason: str | None = None
    error: str | None = None


class PopularStocksResponse(BaseModel):
    """인기 종목 목록 응답"""
    market_cap: list[str]
    volume: list[str]
    total_unique: int


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


# =========================================================================
# Daily Batch Update Endpoints
# =========================================================================


@router.get(
    "/batch/status",
    response_model=BatchUpdateStatusResponse,
    summary="일일 배치 업데이트 상태 조회",
    description="장 마감 후 인기 종목 배치 업데이트의 현재 상태를 조회합니다.",
)
async def get_batch_status() -> BatchUpdateStatusResponse:
    """
    일일 배치 업데이트 상태 조회

    - 현재 배치 업데이트 상태 (idle/running/completed/failed)
    - 최근 실행 기록
    - 다음 예정 실행 시간
    - 배치 업데이트 설정
    """
    status_data = await get_batch_update_status()
    return BatchUpdateStatusResponse(**status_data)


@router.post(
    "/batch/trigger",
    response_model=BatchUpdateTriggerResponse,
    summary="일일 배치 업데이트 수동 트리거",
    description="장 마감 후 인기 종목 배치 업데이트를 수동으로 시작합니다.",
)
async def trigger_batch_update(background_tasks: BackgroundTasks) -> BatchUpdateTriggerResponse:
    """
    일일 배치 업데이트 수동 트리거

    테스트 또는 긴급 상황에서 즉시 배치 업데이트를 실행합니다.
    배치 업데이트는 백그라운드에서 실행되며, 상태는 /batch/status 엔드포인트에서 확인할 수 있습니다.

    대상:
    - 시가총액 상위 100종목
    - 거래량 상위 50종목
    """
    # 백그라운드에서 배치 업데이트 실행
    background_tasks.add_task(trigger_daily_batch_update)

    return BatchUpdateTriggerResponse(
        triggered=True,
        message="Batch update started in background. Check /batch/status for progress.",
    )


@router.post(
    "/batch/trigger-sync",
    response_model=BatchUpdateResultResponse,
    summary="일일 배치 업데이트 동기 실행",
    description="장 마감 후 인기 종목 배치 업데이트를 동기로 실행합니다 (완료까지 대기).",
)
async def trigger_batch_update_sync() -> BatchUpdateResultResponse:
    """
    일일 배치 업데이트 동기 실행

    배치 업데이트가 완료될 때까지 응답을 대기합니다.
    주의: 전체 처리에 수 분이 소요될 수 있습니다.
    """
    result = await trigger_daily_batch_update()
    return BatchUpdateResultResponse(**result)


@router.get(
    "/batch/popular-stocks",
    response_model=PopularStocksResponse,
    summary="배치 업데이트 대상 종목 조회",
    description="배치 업데이트 대상인 인기 종목 목록을 미리 조회합니다.",
)
async def get_batch_target_stocks() -> PopularStocksResponse:
    """
    배치 업데이트 대상 종목 조회

    현재 기준 시가총액/거래량 상위 종목 목록을 반환합니다.
    실제 배치 업데이트 시 이 목록이 대상이 됩니다.
    """
    popular = await get_popular_stocks_for_batch()

    market_cap = popular.get("market_cap", [])
    volume = popular.get("volume", [])
    total_unique = len(set(market_cap + volume))

    return PopularStocksResponse(
        market_cap=market_cap,
        volume=volume,
        total_unique=total_unique,
    )
