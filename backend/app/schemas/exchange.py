"""Exchange rate schemas."""
from datetime import date
from pydantic import BaseModel, Field


class ExchangeRateResponse(BaseModel):
    """Current exchange rate response."""
    rate: float = Field(..., description="USD/KRW exchange rate")
    date: date = Field(..., description="Rate date")
    change: float = Field(..., description="Change from previous day")
    change_percent: float = Field(..., description="Percent change from previous day")


class ExchangeHistoryItem(BaseModel):
    """Single day exchange rate data."""
    date: date
    open: float
    high: float
    low: float
    close: float


class ExchangeHistoryResponse(BaseModel):
    """Exchange rate history response."""
    data: list[ExchangeHistoryItem]
    count: int
