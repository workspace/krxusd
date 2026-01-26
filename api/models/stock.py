from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    SmallInteger,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.core.database import Base


class Stock(Base):
    """
    Stock master information (종목 마스터 정보)

    Stores basic information about listed stocks including
    symbol, name, market, sector, and listing details.
    """

    __tablename__ = "stocks"
    __table_args__ = (
        CheckConstraint("market IN ('KOSPI', 'KOSDAQ', 'KONEX')", name="chk_market"),
        Index("idx_stocks_market", "market"),
        Index("idx_stocks_name", "name"),
        Index("idx_stocks_is_active", "is_active"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(100))
    market: Mapped[str] = mapped_column(String(10), nullable=False)  # KOSPI, KOSDAQ, KONEX
    sector: Mapped[str | None] = mapped_column(String(100))
    industry: Mapped[str | None] = mapped_column(String(100))
    listed_shares: Mapped[int | None] = mapped_column(BigInteger)
    listing_date: Mapped[date | None] = mapped_column(Date)
    fiscal_month: Mapped[int | None] = mapped_column(SmallInteger)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=datetime.utcnow
    )

    # Relationships
    prices: Mapped[list["StockPrice"]] = relationship(
        "StockPrice", back_populates="stock", cascade="all, delete-orphan"
    )
    sync_statuses: Mapped[list["SyncStatus"]] = relationship(
        "SyncStatus", back_populates="stock", cascade="all, delete-orphan"
    )
    popular_rankings: Mapped[list["PopularStock"]] = relationship(
        "PopularStock", back_populates="stock", cascade="all, delete-orphan"
    )


class StockPrice(Base):
    """
    Daily stock price data (일별 종가 데이터)

    Stores OHLCV (Open, High, Low, Close, Volume) data for each trading day,
    along with USD-converted prices using the exchange rate.
    """

    __tablename__ = "stock_prices"
    __table_args__ = (
        UniqueConstraint("stock_id", "price_date", name="uq_stock_prices_stock_date"),
        Index("idx_stock_prices_stock_id", "stock_id"),
        Index("idx_stock_prices_price_date", "price_date"),
        Index("idx_stock_prices_stock_date", "stock_id", "price_date", postgresql_using="btree"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )
    price_date: Mapped[date] = mapped_column(Date, nullable=False)
    open_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    high_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    low_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    close_price: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    volume: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    trading_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    market_cap: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    shares_outstanding: Mapped[int | None] = mapped_column(BigInteger)
    exchange_rate: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    close_price_usd: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    # Relationships
    stock: Mapped["Stock"] = relationship("Stock", back_populates="prices")


class SyncStatus(Base):
    """
    Data synchronization status tracking (데이터 동기화 상태 추적)

    Tracks the last sync date and status for each stock's data types
    to implement the Gap Filling strategy.
    """

    __tablename__ = "sync_status"
    __table_args__ = (
        UniqueConstraint("stock_id", "data_type", name="uq_sync_status_stock_type"),
        CheckConstraint(
            "data_type IN ('daily_price', 'minute_price', 'fundamental')",
            name="chk_data_type",
        ),
        CheckConstraint(
            "status IN ('pending', 'syncing', 'completed', 'failed')",
            name="chk_status",
        ),
        Index("idx_sync_status_stock_id", "stock_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stock_id: Mapped[int | None] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE")
    )
    data_type: Mapped[str] = mapped_column(String(20), nullable=False)
    last_sync_date: Mapped[date | None] = mapped_column(Date)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[str | None] = mapped_column(String(500))

    # Relationships
    stock: Mapped["Stock"] = relationship("Stock", back_populates="sync_statuses")


class PopularStock(Base):
    """
    Popular/Trending stocks cache (인기 종목 캐시)

    Stores daily rankings of popular stocks by various metrics
    (volume, trading value, gain, loss).
    """

    __tablename__ = "popular_stocks"
    __table_args__ = (
        UniqueConstraint(
            "stock_id", "ranking_type", "rank_date", name="uq_popular_stocks"
        ),
        CheckConstraint(
            "ranking_type IN ('volume', 'value', 'gain', 'loss')",
            name="chk_ranking_type",
        ),
        Index("idx_popular_stocks_date_type", "rank_date", "ranking_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    stock_id: Mapped[int] = mapped_column(
        ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False
    )
    ranking_type: Mapped[str] = mapped_column(String(20), nullable=False)
    rank_position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    rank_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)
    metric_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 4))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow
    )

    # Relationships
    stock: Mapped["Stock"] = relationship("Stock", back_populates="popular_rankings")
