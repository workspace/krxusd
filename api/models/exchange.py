from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from api.core.database import Base


class ExchangeRate(Base):
    """
    Exchange rate history (환율 히스토리)

    Stores historical exchange rate data for USD/KRW pair.
    Real-time rates are cached in Redis, while this table
    stores historical records for chart display and calculations.
    """

    __tablename__ = "exchange_rates"
    __table_args__ = (
        UniqueConstraint("currency_pair", "rate_date", name="uq_exchange_rates_pair_date"),
        Index("idx_exchange_rates_pair_date", "currency_pair", "rate_date", postgresql_using="btree"),
        Index("idx_exchange_rates_date", "rate_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    currency_pair: Mapped[str] = mapped_column(String(10), default="USD/KRW", nullable=False)
    rate: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    rate_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
