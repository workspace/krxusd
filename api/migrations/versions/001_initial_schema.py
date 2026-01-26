"""Initial database schema

Revision ID: 001_initial
Revises:
Create Date: 2026-01-27

This migration creates the initial database schema for KRXUSD:
- stocks: Stock master information
- stock_prices: Daily OHLCV data
- exchange_rates: Exchange rate history
- sync_status: Data sync tracking
- popular_stocks: Trending stocks cache
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable uuid extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # Create stocks table
    op.create_table(
        "stocks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("name_en", sa.String(100), nullable=True),
        sa.Column("market", sa.String(10), nullable=False),
        sa.Column("sector", sa.String(100), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("listed_shares", sa.BigInteger(), nullable=True),
        sa.Column("listing_date", sa.Date(), nullable=True),
        sa.Column("fiscal_month", sa.SmallInteger(), nullable=True),
        sa.Column("is_active", sa.Boolean(), default=True, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("symbol"),
        sa.CheckConstraint("market IN ('KOSPI', 'KOSDAQ', 'KONEX')", name="chk_market"),
    )
    op.create_index("idx_stocks_symbol", "stocks", ["symbol"])
    op.create_index("idx_stocks_market", "stocks", ["market"])
    op.create_index("idx_stocks_name", "stocks", ["name"])
    op.create_index("idx_stocks_is_active", "stocks", ["is_active"])

    # Create stock_prices table
    op.create_table(
        "stock_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("price_date", sa.Date(), nullable=False),
        sa.Column("open_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("high_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("low_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("close_price", sa.Numeric(15, 2), nullable=False),
        sa.Column("volume", sa.BigInteger(), default=0, nullable=False),
        sa.Column("trading_value", sa.Numeric(20, 2), nullable=True),
        sa.Column("market_cap", sa.Numeric(20, 2), nullable=True),
        sa.Column("shares_outstanding", sa.BigInteger(), nullable=True),
        sa.Column("exchange_rate", sa.Numeric(15, 4), nullable=True),
        sa.Column("close_price_usd", sa.Numeric(15, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("stock_id", "price_date", name="uq_stock_prices_stock_date"),
    )
    op.create_index("idx_stock_prices_stock_id", "stock_prices", ["stock_id"])
    op.create_index("idx_stock_prices_price_date", "stock_prices", ["price_date"])
    op.create_index(
        "idx_stock_prices_stock_date",
        "stock_prices",
        ["stock_id", "price_date"],
        postgresql_using="btree",
    )

    # Create exchange_rates table
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("currency_pair", sa.String(10), default="USD/KRW", nullable=False),
        sa.Column("rate", sa.Numeric(15, 4), nullable=False),
        sa.Column("rate_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "currency_pair", "rate_date", name="uq_exchange_rates_pair_date"
        ),
    )
    op.create_index(
        "idx_exchange_rates_pair_date",
        "exchange_rates",
        ["currency_pair", "rate_date"],
        postgresql_using="btree",
    )
    op.create_index("idx_exchange_rates_date", "exchange_rates", ["rate_date"])

    # Create sync_status table
    op.create_table(
        "sync_status",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=True),
        sa.Column("data_type", sa.String(20), nullable=False),
        sa.Column("last_sync_date", sa.Date(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), default="pending", nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("stock_id", "data_type", name="uq_sync_status_stock_type"),
        sa.CheckConstraint(
            "data_type IN ('daily_price', 'minute_price', 'fundamental')",
            name="chk_data_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'syncing', 'completed', 'failed')",
            name="chk_status",
        ),
    )
    op.create_index("idx_sync_status_stock_id", "sync_status", ["stock_id"])

    # Create popular_stocks table
    op.create_table(
        "popular_stocks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("stock_id", sa.Integer(), nullable=False),
        sa.Column("ranking_type", sa.String(20), nullable=False),
        sa.Column("rank_position", sa.SmallInteger(), nullable=False),
        sa.Column(
            "rank_date",
            sa.Date(),
            server_default=sa.text("CURRENT_DATE"),
            nullable=False,
        ),
        sa.Column("metric_value", sa.Numeric(20, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "stock_id", "ranking_type", "rank_date", name="uq_popular_stocks"
        ),
        sa.CheckConstraint(
            "ranking_type IN ('volume', 'value', 'gain', 'loss')",
            name="chk_ranking_type",
        ),
    )
    op.create_index(
        "idx_popular_stocks_date_type", "popular_stocks", ["rank_date", "ranking_type"]
    )

    # Create auto-update timestamp function
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $$ language 'plpgsql';
    """)

    # Apply trigger to stocks table
    op.execute("""
        CREATE TRIGGER update_stocks_updated_at
        BEFORE UPDATE ON stocks
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
    """)

    # Insert initial index data
    op.execute("""
        INSERT INTO stocks (symbol, name, name_en, market, sector, is_active) VALUES
            ('KOSPI', 'KOSPI 지수', 'KOSPI Index', 'KOSPI', 'Index', true),
            ('KOSDAQ', 'KOSDAQ 지수', 'KOSDAQ Index', 'KOSDAQ', 'Index', true)
        ON CONFLICT (symbol) DO NOTHING;
    """)


def downgrade() -> None:
    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS update_stocks_updated_at ON stocks")

    # Drop function
    op.execute("DROP FUNCTION IF EXISTS update_updated_at_column()")

    # Drop tables in reverse order
    op.drop_table("popular_stocks")
    op.drop_table("sync_status")
    op.drop_table("exchange_rates")
    op.drop_table("stock_prices")
    op.drop_table("stocks")
