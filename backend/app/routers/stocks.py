"""Stock API router."""
from datetime import date
from typing import Optional

from fastapi import APIRouter, Query, HTTPException

from app.schemas.stock import (
    StockInfo,
    StockSearchResult,
    StockPriceHistory,
    StockUsdPriceHistory,
)
from app.services.stock_service import StockService
from app.services.usd_converter import UsdConverterService

router = APIRouter(prefix="/api/stocks", tags=["Stocks"])
stock_service = StockService()
usd_service = UsdConverterService()


@router.get("/search", response_model=StockSearchResult)
def search_stocks(
    q: str = Query(..., description="Search query (stock name or code)"),
    limit: int = Query(20, ge=1, le=100, description="Maximum results"),
):
    """
    종목 검색.
    
    종목명 또는 코드로 검색합니다.
    
    Args:
        q: 검색어 (종목명 또는 코드)
        limit: 최대 결과 수
        
    Returns:
        검색 결과 리스트
    """
    return stock_service.search(q, limit)


@router.get("/popular", response_model=list[StockInfo])
def get_popular_stocks(
    limit: int = Query(10, ge=1, le=50, description="Maximum results"),
):
    """
    인기 종목 조회.
    
    Returns:
        인기/주요 종목 리스트
    """
    return stock_service.get_popular_stocks(limit)


@router.get("/{code}", response_model=StockInfo)
def get_stock_info(code: str):
    """
    종목 정보 조회.
    
    Args:
        code: 종목 코드 (예: 005930)
        
    Returns:
        종목 기본 정보
    """
    stock = stock_service.get_stock_info(code)
    if stock is None:
        raise HTTPException(status_code=404, detail=f"Stock {code} not found")
    return stock


@router.get("/{code}/history", response_model=list[StockPriceHistory])
def get_stock_history(
    code: str,
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
):
    """
    종목 가격 히스토리 조회.
    
    Args:
        code: 종목 코드
        start: 시작일
        end: 종료일 (기본값: 오늘)
        
    Returns:
        일별 OHLCV 데이터
    """
    history = stock_service.get_history(code, start, end)
    if not history:
        raise HTTPException(status_code=404, detail=f"No history found for {code}")
    return history


@router.get("/{code}/usd", response_model=StockUsdPriceHistory)
def get_stock_usd_history(
    code: str,
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: Optional[date] = Query(None, description="End date (YYYY-MM-DD)"),
):
    """
    [핵심 API] USD 환산 주가 히스토리 조회.
    
    KRW 주가를 해당 일 환율 종가로 나눈 USD 환산 가격을 반환합니다.
    
    계산식: USD 환산 주가 = KRW 주가 / 당일 USD/KRW 환율 종가
    
    Args:
        code: 종목 코드
        start: 시작일
        end: 종료일 (기본값: 오늘)
        
    Returns:
        일별 KRW 가격, 환율, USD 환산 가격 데이터
    """
    history = usd_service.get_usd_converted_history(code, start, end)
    if history is None:
        raise HTTPException(status_code=404, detail=f"Stock {code} not found")
    return history


@router.get("/{code}/usd/current")
def get_stock_current_usd(code: str):
    """
    현재 USD 환산 주가 조회.
    
    Args:
        code: 종목 코드
        
    Returns:
        현재 KRW 가격, 환율, USD 환산 가격
    """
    result = usd_service.get_current_usd_price(code)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Stock {code} not found")
    return result
