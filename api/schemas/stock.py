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
    name_en: str | None = None
    sector: str | None = None
    industry: str | None = None
    is_active: bool = True
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


# =========================================================================
# Real-time Price Schemas
# =========================================================================


class StockRealtimePriceResponse(BaseModel):
    """Real-time stock price response"""

    symbol: str = Field(..., description="Stock ticker symbol")
    open_price: Decimal = Field(..., description="Opening price in KRW")
    high_price: Decimal = Field(..., description="High price in KRW")
    low_price: Decimal = Field(..., description="Low price in KRW")
    close_price: Decimal = Field(..., description="Current/Closing price in KRW")
    volume: int = Field(..., description="Trading volume")
    change: Decimal = Field(..., description="Price change from previous close")
    change_percent: Decimal = Field(..., description="Price change percentage")
    close_price_usd: Decimal | None = Field(None, description="Current price in USD")
    exchange_rate: Decimal | None = Field(None, description="USD/KRW exchange rate")
    price_date: str = Field(..., description="Price date (YYYY-MM-DD)")
    source: str = Field(..., description="Data source (financedatareader, yfinance)")
    updated_at: str = Field(..., description="Last update timestamp")


class StockRealtimeBatchRequest(BaseModel):
    """Request for batch real-time prices"""

    symbols: list[str] = Field(
        ...,
        description="List of stock symbols",
        min_length=1,
        max_length=50,
    )


class StockRealtimeBatchResponse(BaseModel):
    """Response for batch real-time prices"""

    prices: dict[str, StockRealtimePriceResponse | None] = Field(
        ...,
        description="Map of symbol to price data (None if fetch failed)",
    )
    success_count: int = Field(..., description="Number of successfully fetched prices")
    failed_count: int = Field(..., description="Number of failed fetches")
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# =========================================================================
# Sync Request/Response Schemas
# =========================================================================


class StockSyncRequest(BaseModel):
    """Request for syncing stock price data"""

    days: int = Field(
        default=365,
        ge=1,
        le=3650,
        description="Number of days to sync (default: 365, max: 10 years)",
    )
    force_full_sync: bool = Field(
        default=False,
        description="Force full sync ignoring gap analysis",
    )


class StockSyncResponse(BaseModel):
    """Response for stock sync operation"""

    symbol: str = Field(..., description="Stock symbol")
    sync_case: str = Field(
        ...,
        description="Sync case: no_data (Case A), gap_detected (Case B), up_to_date (Case C)",
    )
    synced_count: int = Field(..., description="Number of records synced")
    start_date: str | None = Field(None, description="Sync start date")
    end_date: str | None = Field(None, description="Sync end date")
    source: str | None = Field(None, description="Data source used")
    message: str | None = Field(None, description="Additional message")


class StockBatchSyncRequest(BaseModel):
    """Request for batch sync of multiple stocks"""

    symbols: list[str] = Field(
        ...,
        description="List of stock symbols to sync",
        min_length=1,
        max_length=100,
    )
    days: int = Field(
        default=365,
        ge=1,
        le=3650,
        description="Number of days to sync",
    )
    force_full_sync: bool = Field(
        default=False,
        description="Force full sync for all stocks",
    )


class StockBatchSyncResponse(BaseModel):
    """Response for batch sync operation"""

    total_requested: int = Field(..., description="Total stocks requested")
    success_count: int = Field(..., description="Successfully synced count")
    failed_count: int = Field(..., description="Failed sync count")
    results: list[StockSyncResponse] = Field(..., description="Individual sync results")


# =========================================================================
# Sync Status Schema
# =========================================================================


class SyncStatusResponse(BaseModel):
    """Sync status information"""

    stock_id: int | None = Field(None, description="Stock ID (None for global)")
    data_type: str = Field(..., description="Data type (daily_price, minute_price, fundamental)")
    status: str = Field(..., description="Status (pending, syncing, completed, failed)")
    last_sync_date: date | None = Field(None, description="Last synced date")
    last_sync_at: datetime | None = Field(None, description="Last sync timestamp")
    error_message: str | None = Field(None, description="Error message if failed")

    class Config:
        from_attributes = True
