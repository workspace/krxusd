"""Exchange rate API router."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query

from app.schemas.exchange import ExchangeRateResponse, ExchangeHistoryResponse
from app.services.exchange_service import ExchangeService

router = APIRouter(prefix="/api/exchange", tags=["Exchange Rate"])
service = ExchangeService()


@router.get("/current", response_model=ExchangeRateResponse)
def get_current_rate():
    """
    현재 USD/KRW 환율 조회.
    
    Returns:
        현재 환율, 날짜, 전일 대비 변동
    """
    return service.get_current_rate()


@router.get("/history", response_model=ExchangeHistoryResponse)
def get_exchange_history(
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: Optional[date] = Query(None, description="End date (YYYY-MM-DD), defaults to today"),
):
    """
    환율 히스토리 조회.
    
    Args:
        start: 시작일
        end: 종료일 (기본값: 오늘)
        
    Returns:
        기간 내 일별 환율 데이터
    """
    return service.get_history(start, end)
