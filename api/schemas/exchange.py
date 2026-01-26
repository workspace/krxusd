from datetime import datetime
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

    class Config:
        from_attributes = True
