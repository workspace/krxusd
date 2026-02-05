"""Stock-related schemas."""
import datetime
from pydantic import BaseModel, Field


class StockInfo(BaseModel):
    """Stock basic information."""
    code: str = Field(..., description="Stock code (e.g., 005930)")
    name: str = Field(..., description="Stock name")
    market: str = Field(..., description="Market (KOSPI/KOSDAQ)")
    price: float = Field(..., description="Current price in KRW")
    change: float = Field(..., description="Price change")
    change_percent: float = Field(..., description="Percent change")
    volume: int = Field(..., description="Trading volume")
    market_cap: float | None = Field(None, description="Market cap in KRW")


class StockSearchResult(BaseModel):
    """Stock search result."""
    results: list[StockInfo]
    count: int


class StockPriceHistory(BaseModel):
    """Single day OHLCV data."""
    date: datetime.date
    open: float
    high: float
    low: float
    close: float
    volume: int


class UsdConvertedData(BaseModel):
    """USD converted stock price data - 핵심 데이터 구조."""
    date: datetime.date
    krw_close: float = Field(..., description="KRW closing price")
    exchange_rate: float = Field(..., description="USD/KRW exchange rate")
    usd_close: float = Field(..., description="USD converted price (krw_close / exchange_rate)")


class StockUsdPriceHistory(BaseModel):
    """USD converted stock price history response."""
    code: str
    name: str
    data: list[UsdConvertedData]
    count: int
