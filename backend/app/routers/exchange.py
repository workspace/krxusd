"""Exchange rate API router."""
import math
from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Query

from app.schemas.exchange import ExchangeRateResponse, ExchangeHistoryResponse
from app.services.exchange_service import ExchangeService

router = APIRouter(prefix="/api/exchange", tags=["Exchange Rate"])
service = ExchangeService()


@router.get("/current", response_model=ExchangeRateResponse)
def get_current_rate():
    return service.get_current_rate()


@router.get("/history", response_model=ExchangeHistoryResponse)
def get_exchange_history(
    start: date = Query(..., description="Start date (YYYY-MM-DD)"),
    end: Optional[date] = Query(None, description="End date (YYYY-MM-DD), defaults to today"),
):
    return service.get_history(start, end)


@router.get("/analysis")
def get_exchange_analysis():
    """환율 이동평균 + 백분위 분석. 5년 데이터 기반."""
    end = date.today()
    start = end - timedelta(days=365 * 5)
    history = service.get_history(start, end)

    closes = [d.close for d in history.data]
    if len(closes) < 20:
        return {"error": "insufficient data"}

    current = closes[-1]
    sorted_closes = sorted(closes)
    percentile = (sorted_closes.index(min(sorted_closes, key=lambda x: abs(x - current))) + 1) / len(sorted_closes) * 100

    def ma(values: list[float], window: int) -> float | None:
        if len(values) < window:
            return None
        return sum(values[-window:]) / window

    ma20 = ma(closes, 20)
    ma60 = ma(closes, 60)
    ma120 = ma(closes, 120)
    ma200 = ma(closes, 200)

    high_5y = max(closes)
    low_5y = min(closes)
    high_1y = max(closes[-252:]) if len(closes) >= 252 else max(closes)
    low_1y = min(closes[-252:]) if len(closes) >= 252 else min(closes)

    return {
        "current": current,
        "percentile_5y": round(percentile, 1),
        "ma20": round(ma20, 2) if ma20 else None,
        "ma60": round(ma60, 2) if ma60 else None,
        "ma120": round(ma120, 2) if ma120 else None,
        "ma200": round(ma200, 2) if ma200 else None,
        "high_5y": high_5y,
        "low_5y": low_5y,
        "high_1y": high_1y,
        "low_1y": low_1y,
        "data_points": len(closes),
    }
