from datetime import datetime, date
from decimal import Decimal
from pydantic import BaseModel, Field


class ExchangeRateBase(BaseModel):
    """Base exchange rate schema"""

    currency_pair: str = Field(default="USD/KRW", description="Currency pair")
    rate: Decimal = Field(..., description="Exchange rate")


class ExchangeRateResponse(ExchangeRateBase):
    """Exchange rate response"""

    id: int | None = None
    rate_date: datetime
    change: Decimal | None = Field(None, description="Change from previous rate")
    change_percent: Decimal | None = Field(None, description="Change percentage")
    source: str | None = Field(None, description="Data source")

    class Config:
        from_attributes = True


class ExchangeRateRealtimeResponse(BaseModel):
    """Real-time exchange rate response (from cache)"""

    rate: Decimal = Field(..., description="Current exchange rate")
    currency_pair: str = Field(default="USD/KRW", description="Currency pair")
    source: str = Field(..., description="Data source (yfinance, eximbank)")
    updated_at: datetime = Field(..., description="Last update timestamp")
    change: Decimal | None = Field(None, description="Change from previous rate")
    change_percent: Decimal | None = Field(None, description="Change percentage")


class ExchangeRateSyncRequest(BaseModel):
    """Request schema for syncing historical rates"""

    days: int = Field(default=30, ge=1, le=365, description="Number of days to sync")


class ExchangeRateSyncResponse(BaseModel):
    """Response schema for sync operation"""

    synced_count: int = Field(..., description="Number of records synced")
    start_date: date = Field(..., description="Sync start date")
    end_date: date = Field(..., description="Sync end date")
    source: str = Field(..., description="Data source used")


class ExchangeRateHistoryRequest(BaseModel):
    """Request schema for fetching historical rates"""

    start_date: date = Field(..., description="Start date for history")
    end_date: date | None = Field(None, description="End date (defaults to today)")


class ConvertCurrencyRequest(BaseModel):
    """Request schema for currency conversion"""

    amount: Decimal = Field(..., gt=0, description="Amount to convert")
    from_currency: str = Field(default="KRW", description="Source currency (KRW or USD)")
    to_currency: str = Field(default="USD", description="Target currency (KRW or USD)")


class ConvertCurrencyResponse(BaseModel):
    """Response schema for currency conversion"""

    original_amount: Decimal = Field(..., description="Original amount")
    original_currency: str = Field(..., description="Original currency")
    converted_amount: Decimal = Field(..., description="Converted amount")
    converted_currency: str = Field(..., description="Converted currency")
    exchange_rate: Decimal = Field(..., description="Exchange rate used")
    rate_date: datetime = Field(..., description="Rate date/time")
