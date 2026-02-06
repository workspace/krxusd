"""Stock API router."""
import math
from datetime import date, timedelta
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


@router.get("/compare/usd")
def compare_stocks_usd(
    codes: str = Query(..., description="Comma-separated stock codes"),
    start: date = Query(default=None),
    end: Optional[date] = Query(None),
):
    """다중 종목 USD 정규화 비교."""
    if start is None:
        start = date.today() - timedelta(days=90)
    code_list = [c.strip() for c in codes.split(",") if c.strip()]
    if len(code_list) < 1 or len(code_list) > 10:
        raise HTTPException(status_code=400, detail="1~10 codes required")

    results = {}
    for code in code_list:
        hist = usd_service.get_usd_converted_history(code, start, end)
        if hist and hist.data:
            base = hist.data[0].usd_close
            results[code] = {
                "name": hist.name,
                "data": [
                    {"date": d.date.isoformat() if hasattr(d.date, 'isoformat') else d.date,
                     "usd": round(d.usd_close, 4),
                     "krw": round(d.krw_close, 0),
                     "normalized": round((d.usd_close / base) * 100, 2) if base else 100}
                    for d in hist.data
                ],
            }

    return {"codes": code_list, "stocks": results}


@router.get("/index/usd")
def get_index_usd(
    index: str = Query("KS11", description="KS11=KOSPI, KQ11=KOSDAQ"),
    period: str = Query("1Y"),
):
    """KOSPI/KOSDAQ 지수 USD 환산."""
    periods = {"1M": 30, "3M": 90, "6M": 180, "1Y": 365, "5Y": 365 * 5}
    days = periods.get(period, 365)
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    try:
        import FinanceDataReader as fdr
        idx_df = fdr.DataReader(index, start_date.isoformat(), end_date.isoformat())
        fx_df = fdr.DataReader('USD/KRW', start_date.isoformat(), end_date.isoformat())

        if idx_df.empty or fx_df.empty:
            raise HTTPException(status_code=404, detail="No data")

        idx_df = idx_df.dropna(subset=['Close'])
        fx_df = fx_df.dropna(subset=['Close'])

        fx_map = {}
        for idx_d, row in fx_df.iterrows():
            fx_map[idx_d.date()] = float(row['Close'])

        data = []
        for idx_d, row in idx_df.iterrows():
            d = idx_d.date()
            rate = fx_map.get(d)
            if rate is None:
                for i in range(1, 5):
                    prev = d - timedelta(days=i)
                    if prev in fx_map:
                        rate = fx_map[prev]
                        break
            if rate is None:
                continue

            krw_close = float(row['Close'])
            usd_close = krw_close / rate
            data.append({
                "date": d.isoformat(),
                "krw_close": round(krw_close, 2),
                "usd_close": round(usd_close, 4),
                "exchange_rate": round(rate, 2),
            })

        if not data:
            raise HTTPException(status_code=404, detail="No matched data")

        first_krw = data[0]["krw_close"]
        first_usd = data[0]["usd_close"]
        last_krw = data[-1]["krw_close"]
        last_usd = data[-1]["usd_close"]

        return {
            "index": index,
            "name": "KOSPI" if index == "KS11" else "KOSDAQ" if index == "KQ11" else index,
            "period": period,
            "current_krw": last_krw,
            "current_usd": round(last_usd, 2),
            "change_krw": round(((last_krw - first_krw) / first_krw) * 100, 2),
            "change_usd": round(((last_usd - first_usd) / first_usd) * 100, 2),
            "fx_effect": round(((last_usd - first_usd) / first_usd) * 100 - ((last_krw - first_krw) / first_krw) * 100, 2),
            "data": data,
            "count": len(data),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
    result = usd_service.get_current_usd_price(code)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Stock {code} not found")
    return result


@router.get("/{code}/correlation")
def get_stock_fx_correlation(
    code: str,
    start: date = Query(default=None),
):
    """주가-환율 상관관계 (-1 ~ +1)."""
    if start is None:
        start = date.today() - timedelta(days=365)
    end = date.today()

    stock_hist = stock_service.get_history(code, start, end)
    from app.services.exchange_service import ExchangeService
    fx_hist = ExchangeService().get_history(start, end)

    fx_map = {d.date: d.close for d in fx_hist.data}

    stock_returns = []
    fx_returns = []
    prev_price = None
    prev_rate = None

    for day in stock_hist:
        rate = fx_map.get(day.date)
        if rate is None:
            continue
        if prev_price is not None and prev_rate is not None:
            stock_returns.append((day.close - prev_price) / prev_price)
            fx_returns.append((rate - prev_rate) / prev_rate)
        prev_price = day.close
        prev_rate = rate

    if len(stock_returns) < 20:
        return {"correlation": None, "sample_size": len(stock_returns)}

    n = len(stock_returns)
    mean_s = sum(stock_returns) / n
    mean_f = sum(fx_returns) / n
    cov = sum((s - mean_s) * (f - mean_f) for s, f in zip(stock_returns, fx_returns)) / (n - 1)
    std_s = math.sqrt(sum((s - mean_s) ** 2 for s in stock_returns) / (n - 1))
    std_f = math.sqrt(sum((f - mean_f) ** 2 for f in fx_returns) / (n - 1))

    corr = cov / (std_s * std_f) if std_s > 0 and std_f > 0 else 0

    return {
        "correlation": round(corr, 3),
        "sample_size": n,
        "interpretation": "수출주 (환율↑=주가↑)" if corr > 0.3 else "내수주 (환율↑=주가↓)" if corr < -0.3 else "환율 영향 약함",
    }
