from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base


class ExchangeRate(Base):
    """Exchange rate history"""

    __tablename__ = "exchange_rates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    currency_pair: Mapped[str] = mapped_column(String(10), default="USD/KRW")
    rate: Mapped[Decimal] = mapped_column(Numeric(15, 4))
    rate_date: Mapped[datetime] = mapped_column(DateTime, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
