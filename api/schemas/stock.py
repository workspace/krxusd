from datetime import date, datetime
from decimal import Decimal
from pydantic import BaseModel, Field


class StockBase(BaseModel):
    """Base stock schema"""

    symbol: str = Field(..., description="Stock ticker symbol (e.g., 005930)")
    name: str = Field(..., description="Stock name (e.g., Samsung Electronics)")
    market: str = Field(..., description="Market type (KOSPI/KOSDAQ)")


class StockCreate(StockBase):
    """Schema for creating a new stock"""

    pass


class StockResponse(StockBase):
    """Stock response with additional fields"""

    id: int
    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class StockPriceBase(BaseModel):
    """Base stock price schema"""

    open_price: Decimal = Field(..., description="Opening price in KRW")
    high_price: Decimal = Field(..., description="High price in KRW")
    low_price: Decimal = Field(..., description="Low price in KRW")
    close_price: Decimal = Field(..., description="Closing price in KRW")
    volume: int = Field(..., description="Trading volume")


class StockPriceResponse(StockPriceBase):
    """Stock price response with USD conversion"""

    id: int
    stock_id: int
    price_date: date
    close_price_usd: Decimal | None = Field(None, description="Closing price in USD")
    exchange_rate: Decimal | None = Field(None, description="KRW/USD exchange rate")
    change_percent: Decimal | None = Field(None, description="Price change percentage")

    class Config:
        from_attributes = True


class StockDetailResponse(BaseModel):
    """Detailed stock information with current price"""

    stock: StockResponse
    current_price: StockPriceResponse | None = None
    market_cap_krw: Decimal | None = Field(None, description="Market cap in KRW")
    market_cap_usd: Decimal | None = Field(None, description="Market cap in USD")
