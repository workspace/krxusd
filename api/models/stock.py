from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Index, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


class Stock(Base):
    """Stock master information"""

    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    market: Mapped[str] = mapped_column(String(10))  # KOSPI, KOSDAQ
    sector: Mapped[str | None] = mapped_column(String(100))
    listed_shares: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, onupdate=datetime.utcnow)

    prices: Mapped[list["StockPrice"]] = relationship("StockPrice", back_populates="stock")


class StockPrice(Base):
    """Daily stock price data"""

    __tablename__ = "stock_prices"
    __table_args__ = (
        Index("ix_stock_prices_stock_date", "stock_id", "price_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(ForeignKey("stocks.id", ondelete="CASCADE"))
    price_date: Mapped[date] = mapped_column(Date, index=True)
    open_price: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    high_price: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    low_price: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    close_price: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    volume: Mapped[int] = mapped_column(BigInteger)
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    close_price_usd: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))

    stock: Mapped["Stock"] = relationship("Stock", back_populates="prices")
