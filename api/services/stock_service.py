"""
Stock Data Collection Service

Collects KRX (Korea Exchange) stock price data using multiple sources:
1. FinanceDataReader - Primary source for KRX stocks
2. yfinance - Secondary/backup source

Implements Gap Filling strategy for data synchronization:
- Case A: No data exists -> Full collection
- Case B: Gap detected -> Collect only missing dates
- Case C: Up to date -> No action needed

Redis caching for real-time data, PostgreSQL for historical data.
"""

import logging
from datetime import datetime, timedelta, date
from decimal import Decimal, InvalidOperation
from typing import Any
from enum import Enum

import FinanceDataReader as fdr
import yfinance as yf
import pandas as pd
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from api.core.redis import (
    stock_realtime_cache,
    stock_minute_cache,
    exchange_rate_cache,
    cache,
)
from api.models.stock import Stock, StockPrice, SyncStatus

logger = logging.getLogger(__name__)

# Constants
CACHE_TTL_REALTIME = 120  # 2 minutes for real-time stock price
CACHE_TTL_DAILY = 300  # 5 minutes for daily data
DEFAULT_HISTORY_DAYS = 365  # Default days to fetch for initial sync


class SyncCase(Enum):
    """Gap Filling sync cases"""
    CASE_A_NO_DATA = "no_data"  # Full collection needed
    CASE_B_GAP_DETECTED = "gap_detected"  # Partial collection needed
    CASE_C_UP_TO_DATE = "up_to_date"  # No action needed


class StockDataServiceError(Exception):
    """Base exception for stock data service"""
    pass


class StockNotFoundError(StockDataServiceError):
    """Stock symbol not found"""
    pass


class StockDataFetchError(StockDataServiceError):
    """Failed to fetch stock data from any source"""
    pass


class StockDataService:
    """
    Service for collecting and managing KRX stock price data.

    Features:
    - Fetches real-time prices from FinanceDataReader or yfinance
    - Caches prices in Redis (2-minute TTL)
    - Stores historical prices in PostgreSQL
    - Implements Gap Filling strategy for efficient sync
    - Provides USD conversion using exchange rate
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def close(self) -> None:
        """Cleanup resources"""
        pass  # No HTTP client to close for this service

    # =========================================================================
    # Stock Master Data
    # =========================================================================

    async def get_stock_by_symbol(self, symbol: str) -> Stock | None:
        """
        Get stock by symbol from database.

        Args:
            symbol: Stock ticker symbol (e.g., '005930' for Samsung)

        Returns:
            Stock model or None if not found
        """
        query = select(Stock).where(Stock.symbol == symbol.upper())
        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create_stock(
        self,
        symbol: str,
        name: str | None = None,
        market: str = "KOSPI",
    ) -> Stock:
        """
        Get existing stock or create new one.

        Args:
            symbol: Stock ticker symbol
            name: Stock name (fetched if not provided)
            market: Market type (KOSPI/KOSDAQ/KONEX)

        Returns:
            Stock model instance
        """
        stock = await self.get_stock_by_symbol(symbol)
        if stock:
            return stock

        # Fetch stock info if name not provided
        if not name:
            stock_info = await self._fetch_stock_info(symbol)
            name = stock_info.get("name", symbol)
            market = stock_info.get("market", market)

        # Create new stock
        stock = Stock(
            symbol=symbol.upper(),
            name=name,
            market=market,
            is_active=True,
        )
        self.db.add(stock)
        await self.db.commit()
        await self.db.refresh(stock)

        logger.info(f"Created new stock: {symbol} ({name})")
        return stock

    async def _fetch_stock_info(self, symbol: str) -> dict[str, Any]:
        """
        Fetch stock information from external source.

        Args:
            symbol: Stock ticker symbol

        Returns:
            dict with stock info (name, market, etc.)
        """
        try:
            # Try to get stock list and find the symbol
            krx_stocks = fdr.StockListing("KRX")
            stock_row = krx_stocks[krx_stocks["Code"] == symbol]

            if not stock_row.empty:
                row = stock_row.iloc[0]
                return {
                    "name": row.get("Name", symbol),
                    "market": row.get("Market", "KOSPI"),
                    "sector": row.get("Sector"),
                    "industry": row.get("Industry"),
                }
        except Exception as e:
            logger.warning(f"Failed to fetch stock info for {symbol}: {e}")

        # Return default values
        return {"name": symbol, "market": "KOSPI"}

    # =========================================================================
    # Real-time Price Fetching
    # =========================================================================

    async def get_realtime_price(
        self,
        symbol: str,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        Get real-time stock price with Redis caching.

        Args:
            symbol: Stock ticker symbol
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            dict with price data (open, high, low, close, volume, etc.)
        """
        symbol = symbol.upper()

        # Check Redis cache first (unless force refresh)
        if not force_refresh:
            cached = await stock_realtime_cache.get(symbol)
            if cached:
                logger.debug(f"Stock price retrieved from cache: {symbol}")
                return cached

        # Fetch from external source
        price_data = await self._fetch_realtime_from_sources(symbol)

        # Get current exchange rate for USD conversion
        exchange_data = await exchange_rate_cache.get_realtime()
        if exchange_data:
            exchange_rate = Decimal(exchange_data["rate"])
            close_price = Decimal(str(price_data["close_price"]))
            price_data["exchange_rate"] = str(exchange_rate)
            price_data["close_price_usd"] = str(
                round(close_price / exchange_rate, 4)
            )

        # Update Redis cache
        await stock_realtime_cache.set(symbol, price_data)

        logger.info(f"Stock price fetched and cached: {symbol}")
        return price_data

    async def get_realtime_prices_batch(
        self,
        symbols: list[str],
        force_refresh: bool = False,
    ) -> dict[str, dict[str, Any] | None]:
        """
        Get real-time prices for multiple stocks.

        Args:
            symbols: List of stock symbols
            force_refresh: If True, bypass cache

        Returns:
            dict mapping symbols to price data
        """
        symbols = [s.upper() for s in symbols]
        results: dict[str, dict[str, Any] | None] = {}

        # Check cache first
        if not force_refresh:
            cached = await stock_realtime_cache.mget(symbols)
            for symbol, data in cached.items():
                if data:
                    results[symbol] = data

        # Fetch missing symbols
        missing = [s for s in symbols if s not in results]
        if missing:
            # Get exchange rate once
            exchange_data = await exchange_rate_cache.get_realtime()
            exchange_rate = (
                Decimal(exchange_data["rate"]) if exchange_data else None
            )

            for symbol in missing:
                try:
                    price_data = await self._fetch_realtime_from_sources(symbol)
                    if exchange_rate:
                        close_price = Decimal(str(price_data["close_price"]))
                        price_data["exchange_rate"] = str(exchange_rate)
                        price_data["close_price_usd"] = str(
                            round(close_price / exchange_rate, 4)
                        )
                    results[symbol] = price_data
                except Exception as e:
                    logger.warning(f"Failed to fetch price for {symbol}: {e}")
                    results[symbol] = None

            # Update cache for fetched prices
            to_cache = {s: d for s, d in results.items() if d and s in missing}
            if to_cache:
                await stock_realtime_cache.mset(to_cache)

        return results

    async def _fetch_realtime_from_sources(
        self,
        symbol: str,
    ) -> dict[str, Any]:
        """
        Try to fetch real-time price from multiple sources.

        Args:
            symbol: Stock ticker symbol

        Returns:
            dict with price data
        """
        errors = []

        # Try FinanceDataReader first (better for KRX stocks)
        try:
            return await self._fetch_from_fdr(symbol)
        except Exception as e:
            errors.append(f"FinanceDataReader: {str(e)}")
            logger.warning(f"Failed to fetch from FDR for {symbol}: {e}")

        # Try yfinance as backup (KRX symbols need .KS or .KQ suffix)
        try:
            return await self._fetch_from_yfinance(symbol)
        except Exception as e:
            errors.append(f"yfinance: {str(e)}")
            logger.warning(f"Failed to fetch from yfinance for {symbol}: {e}")

        # All sources failed
        raise StockDataFetchError(
            f"Failed to fetch stock data for {symbol} from all sources: "
            f"{'; '.join(errors)}"
        )

    async def _fetch_from_fdr(self, symbol: str) -> dict[str, Any]:
        """
        Fetch real-time price from FinanceDataReader.

        Args:
            symbol: Stock ticker symbol

        Returns:
            dict with price data
        """
        try:
            # Get today's data (or most recent trading day)
            end_date = date.today()
            start_date = end_date - timedelta(days=7)  # Look back a week

            df = fdr.DataReader(symbol, start_date, end_date)

            if df.empty:
                raise ValueError(f"No data returned for {symbol}")

            # Get the most recent row
            latest = df.iloc[-1]
            price_date = df.index[-1]

            # Handle different column name formats
            open_price = latest.get("Open", latest.get("open", 0))
            high_price = latest.get("High", latest.get("high", 0))
            low_price = latest.get("Low", latest.get("low", 0))
            close_price = latest.get("Close", latest.get("close", 0))
            volume = latest.get("Volume", latest.get("volume", 0))

            # Calculate change
            if len(df) > 1:
                prev_close = df.iloc[-2].get(
                    "Close", df.iloc[-2].get("close", close_price)
                )
                change = float(close_price) - float(prev_close)
                change_percent = (
                    (change / float(prev_close)) * 100 if prev_close else 0
                )
            else:
                change = 0
                change_percent = 0

            return {
                "symbol": symbol,
                "open_price": str(round(float(open_price), 2)),
                "high_price": str(round(float(high_price), 2)),
                "low_price": str(round(float(low_price), 2)),
                "close_price": str(round(float(close_price), 2)),
                "volume": int(volume),
                "change": str(round(change, 2)),
                "change_percent": str(round(change_percent, 2)),
                "price_date": price_date.strftime("%Y-%m-%d"),
                "source": "financedatareader",
                "updated_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"FDR fetch error for {symbol}: {e}")
            raise

    async def _fetch_from_yfinance(self, symbol: str) -> dict[str, Any]:
        """
        Fetch real-time price from Yahoo Finance.

        Args:
            symbol: Stock ticker symbol

        Returns:
            dict with price data
        """
        try:
            # Determine Yahoo Finance symbol suffix based on market
            stock = await self.get_stock_by_symbol(symbol)
            if stock and stock.market == "KOSDAQ":
                yf_symbol = f"{symbol}.KQ"
            else:
                yf_symbol = f"{symbol}.KS"  # Default to KOSPI

            ticker = yf.Ticker(yf_symbol)

            # Try fast_info first for real-time data
            info = ticker.fast_info
            if hasattr(info, "last_price") and info.last_price:
                close_price = info.last_price
                open_price = info.open if hasattr(info, "open") else close_price
                high_price = (
                    info.day_high if hasattr(info, "day_high") else close_price
                )
                low_price = (
                    info.day_low if hasattr(info, "day_low") else close_price
                )
                volume = (
                    info.last_volume if hasattr(info, "last_volume") else 0
                )
                prev_close = (
                    info.previous_close
                    if hasattr(info, "previous_close")
                    else close_price
                )
            else:
                # Fallback to history
                hist = ticker.history(period="5d", interval="1d")
                if hist.empty:
                    raise ValueError(f"No data returned for {yf_symbol}")

                latest = hist.iloc[-1]
                open_price = latest["Open"]
                high_price = latest["High"]
                low_price = latest["Low"]
                close_price = latest["Close"]
                volume = int(latest["Volume"])
                prev_close = (
                    hist.iloc[-2]["Close"] if len(hist) > 1 else close_price
                )

            change = float(close_price) - float(prev_close)
            change_percent = (
                (change / float(prev_close)) * 100 if prev_close else 0
            )

            return {
                "symbol": symbol,
                "open_price": str(round(float(open_price), 2)),
                "high_price": str(round(float(high_price), 2)),
                "low_price": str(round(float(low_price), 2)),
                "close_price": str(round(float(close_price), 2)),
                "volume": int(volume),
                "change": str(round(change, 2)),
                "change_percent": str(round(change_percent, 2)),
                "price_date": date.today().isoformat(),
                "source": "yfinance",
                "updated_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"yfinance fetch error for {symbol}: {e}")
            raise

    # =========================================================================
    # Gap Filling Strategy Implementation
    # =========================================================================

    async def analyze_sync_status(
        self,
        stock_id: int,
        data_type: str = "daily_price",
    ) -> tuple[SyncCase, date | None, date | None]:
        """
        Analyze sync status to determine gap filling case.

        Args:
            stock_id: Stock database ID
            data_type: Type of data to analyze ('daily_price', etc.)

        Returns:
            Tuple of (SyncCase, start_date_to_sync, end_date_to_sync)
            - Case A: Returns (CASE_A, oldest_needed_date, today)
            - Case B: Returns (CASE_B, gap_start_date, today)
            - Case C: Returns (CASE_C, None, None)
        """
        today = date.today()

        # Get the latest price date from database
        query = (
            select(func.max(StockPrice.price_date))
            .where(StockPrice.stock_id == stock_id)
        )
        result = await self.db.execute(query)
        last_price_date = result.scalar_one_or_none()

        # Case A: No data exists
        if last_price_date is None:
            start_date = today - timedelta(days=DEFAULT_HISTORY_DAYS)
            logger.info(
                f"Stock {stock_id}: Case A - No data, full collection from {start_date}"
            )
            return SyncCase.CASE_A_NO_DATA, start_date, today

        # Check if we need to sync (gap exists or not up to date)
        # Note: We check against "today - 1" for business days consideration
        # but fetch up to today to account for potential market open
        if last_price_date >= today - timedelta(days=1):
            # Case C: Up to date (within 1 day tolerance for weekends)
            logger.info(f"Stock {stock_id}: Case C - Up to date ({last_price_date})")
            return SyncCase.CASE_C_UP_TO_DATE, None, None

        # Case B: Gap detected
        # Start from the day after last price date
        gap_start = last_price_date + timedelta(days=1)
        logger.info(
            f"Stock {stock_id}: Case B - Gap detected, sync from {gap_start} to {today}"
        )
        return SyncCase.CASE_B_GAP_DETECTED, gap_start, today

    async def sync_stock_prices(
        self,
        symbol: str,
        start_date: date | None = None,
        end_date: date | None = None,
        force_full_sync: bool = False,
    ) -> dict[str, Any]:
        """
        Sync stock prices using Gap Filling strategy.

        Args:
            symbol: Stock ticker symbol
            start_date: Optional start date (auto-determined if not provided)
            end_date: Optional end date (defaults to today)
            force_full_sync: If True, ignore gap analysis and do full sync

        Returns:
            dict with sync result details
        """
        symbol = symbol.upper()

        # Get or create stock record
        stock = await self.get_or_create_stock(symbol)

        # Determine sync range using gap filling strategy
        if start_date is None and not force_full_sync:
            sync_case, start_date, end_date = await self.analyze_sync_status(
                stock.id
            )

            if sync_case == SyncCase.CASE_C_UP_TO_DATE:
                return {
                    "symbol": symbol,
                    "sync_case": sync_case.value,
                    "synced_count": 0,
                    "message": "Already up to date",
                }
        else:
            if force_full_sync:
                start_date = (
                    start_date
                    or date.today() - timedelta(days=DEFAULT_HISTORY_DAYS)
                )
                sync_case = SyncCase.CASE_A_NO_DATA
            else:
                sync_case = SyncCase.CASE_B_GAP_DETECTED

        if end_date is None:
            end_date = date.today()

        # Update sync status to 'syncing'
        await self._update_sync_status(stock.id, "daily_price", "syncing")

        try:
            # Fetch historical prices
            historical_data = await self._fetch_historical_prices(
                symbol, start_date, end_date
            )

            if not historical_data:
                await self._update_sync_status(
                    stock.id, "daily_price", "completed",
                    last_sync_date=end_date
                )
                return {
                    "symbol": symbol,
                    "sync_case": sync_case.value,
                    "synced_count": 0,
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "message": "No data available for the period",
                }

            # Get exchange rates for USD conversion
            exchange_rates = await self._get_exchange_rates_for_dates(
                [d["price_date"] for d in historical_data]
            )

            # Save to database
            synced_count = await self._save_prices_batch(
                stock.id, historical_data, exchange_rates
            )

            # Update sync status to 'completed'
            await self._update_sync_status(
                stock.id, "daily_price", "completed",
                last_sync_date=end_date
            )

            logger.info(
                f"Synced {synced_count} prices for {symbol} "
                f"({start_date} to {end_date})"
            )

            return {
                "symbol": symbol,
                "sync_case": sync_case.value,
                "synced_count": synced_count,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "source": historical_data[0].get("source", "unknown"),
            }

        except Exception as e:
            # Update sync status to 'failed'
            await self._update_sync_status(
                stock.id, "daily_price", "failed",
                error_message=str(e)[:500]
            )
            raise

    async def _fetch_historical_prices(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """
        Fetch historical prices from external sources.

        Args:
            symbol: Stock ticker symbol
            start_date: Start date
            end_date: End date

        Returns:
            List of price data dictionaries
        """
        errors = []

        # Try FinanceDataReader first
        try:
            return await self._fetch_historical_from_fdr(
                symbol, start_date, end_date
            )
        except Exception as e:
            errors.append(f"FDR: {str(e)}")
            logger.warning(f"FDR historical fetch failed for {symbol}: {e}")

        # Try yfinance as backup
        try:
            return await self._fetch_historical_from_yfinance(
                symbol, start_date, end_date
            )
        except Exception as e:
            errors.append(f"yfinance: {str(e)}")
            logger.warning(f"yfinance historical fetch failed for {symbol}: {e}")

        raise StockDataFetchError(
            f"Failed to fetch historical data for {symbol}: {'; '.join(errors)}"
        )

    async def _fetch_historical_from_fdr(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch historical prices from FinanceDataReader."""
        df = fdr.DataReader(symbol, start_date, end_date)

        if df.empty:
            logger.warning(f"No FDR data for {symbol} ({start_date} to {end_date})")
            return []

        prices = []
        for idx, row in df.iterrows():
            price_date = idx.date() if hasattr(idx, "date") else idx

            # Handle different column name formats
            open_price = row.get("Open", row.get("open", 0))
            high_price = row.get("High", row.get("high", 0))
            low_price = row.get("Low", row.get("low", 0))
            close_price = row.get("Close", row.get("close", 0))
            volume = row.get("Volume", row.get("volume", 0))

            prices.append({
                "price_date": price_date,
                "open_price": Decimal(str(round(float(open_price), 2))),
                "high_price": Decimal(str(round(float(high_price), 2))),
                "low_price": Decimal(str(round(float(low_price), 2))),
                "close_price": Decimal(str(round(float(close_price), 2))),
                "volume": int(volume),
                "source": "financedatareader",
            })

        return prices

    async def _fetch_historical_from_yfinance(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[dict[str, Any]]:
        """Fetch historical prices from Yahoo Finance."""
        # Determine Yahoo Finance symbol suffix
        stock = await self.get_stock_by_symbol(symbol)
        if stock and stock.market == "KOSDAQ":
            yf_symbol = f"{symbol}.KQ"
        else:
            yf_symbol = f"{symbol}.KS"

        ticker = yf.Ticker(yf_symbol)
        df = ticker.history(
            start=start_date.isoformat(),
            end=(end_date + timedelta(days=1)).isoformat(),
            interval="1d",
        )

        if df.empty:
            logger.warning(
                f"No yfinance data for {yf_symbol} ({start_date} to {end_date})"
            )
            return []

        prices = []
        for idx, row in df.iterrows():
            price_date = idx.date() if hasattr(idx, "date") else idx.to_pydatetime().date()

            prices.append({
                "price_date": price_date,
                "open_price": Decimal(str(round(row["Open"], 2))),
                "high_price": Decimal(str(round(row["High"], 2))),
                "low_price": Decimal(str(round(row["Low"], 2))),
                "close_price": Decimal(str(round(row["Close"], 2))),
                "volume": int(row["Volume"]),
                "source": "yfinance",
            })

        return prices

    async def _save_prices_batch(
        self,
        stock_id: int,
        prices: list[dict[str, Any]],
        exchange_rates: dict[date, Decimal],
    ) -> int:
        """
        Save prices to database in batch with upsert.

        Args:
            stock_id: Stock database ID
            prices: List of price dictionaries
            exchange_rates: Map of date to exchange rate

        Returns:
            Number of records saved
        """
        count = 0
        for price_data in prices:
            price_date = price_data["price_date"]
            exchange_rate = exchange_rates.get(price_date)

            # Calculate USD price if exchange rate available
            close_price_usd = None
            if exchange_rate:
                close_price_usd = round(
                    price_data["close_price"] / exchange_rate, 4
                )

            stmt = insert(StockPrice).values(
                stock_id=stock_id,
                price_date=price_date,
                open_price=price_data["open_price"],
                high_price=price_data["high_price"],
                low_price=price_data["low_price"],
                close_price=price_data["close_price"],
                volume=price_data["volume"],
                exchange_rate=exchange_rate,
                close_price_usd=close_price_usd,
            ).on_conflict_do_update(
                constraint="uq_stock_prices_stock_date",
                set_={
                    "open_price": price_data["open_price"],
                    "high_price": price_data["high_price"],
                    "low_price": price_data["low_price"],
                    "close_price": price_data["close_price"],
                    "volume": price_data["volume"],
                    "exchange_rate": exchange_rate,
                    "close_price_usd": close_price_usd,
                }
            )

            await self.db.execute(stmt)
            count += 1

        await self.db.commit()
        return count

    async def _get_exchange_rates_for_dates(
        self,
        dates: list[date],
    ) -> dict[date, Decimal]:
        """
        Get exchange rates for given dates from database.

        Args:
            dates: List of dates to get rates for

        Returns:
            Dict mapping date to exchange rate
        """
        from api.models.exchange import ExchangeRate

        if not dates:
            return {}

        min_date = min(dates)
        max_date = max(dates)

        query = (
            select(ExchangeRate)
            .where(
                and_(
                    ExchangeRate.currency_pair == "USD/KRW",
                    ExchangeRate.rate_date >= datetime.combine(
                        min_date, datetime.min.time()
                    ),
                    ExchangeRate.rate_date <= datetime.combine(
                        max_date, datetime.max.time()
                    ),
                )
            )
        )

        result = await self.db.execute(query)
        rates = result.scalars().all()

        # Map rates to dates (use date part only)
        rate_map: dict[date, Decimal] = {}
        for rate in rates:
            rate_date = rate.rate_date.date() if isinstance(
                rate.rate_date, datetime
            ) else rate.rate_date
            # Keep the latest rate for each date
            rate_map[rate_date] = rate.rate

        # Fill missing dates with nearest available rate
        if rate_map:
            sorted_dates = sorted(rate_map.keys())
            for d in dates:
                if d not in rate_map:
                    # Find nearest earlier date
                    earlier = [rd for rd in sorted_dates if rd <= d]
                    if earlier:
                        rate_map[d] = rate_map[earlier[-1]]
                    elif sorted_dates:
                        # Use earliest available
                        rate_map[d] = rate_map[sorted_dates[0]]

        return rate_map

    async def _update_sync_status(
        self,
        stock_id: int,
        data_type: str,
        status: str,
        last_sync_date: date | None = None,
        error_message: str | None = None,
    ) -> None:
        """Update sync status for a stock."""
        stmt = insert(SyncStatus).values(
            stock_id=stock_id,
            data_type=data_type,
            status=status,
            last_sync_date=last_sync_date,
            last_sync_at=datetime.now() if status in ("completed", "failed") else None,
            error_message=error_message,
        ).on_conflict_do_update(
            constraint="uq_sync_status_stock_type",
            set_={
                "status": status,
                "last_sync_date": last_sync_date or SyncStatus.last_sync_date,
                "last_sync_at": datetime.now() if status in ("completed", "failed") else SyncStatus.last_sync_at,
                "error_message": error_message,
            }
        )

        await self.db.execute(stmt)
        await self.db.commit()

    # =========================================================================
    # Historical Data Retrieval
    # =========================================================================

    async def get_price_history(
        self,
        symbol: str,
        days: int = 30,
        include_usd: bool = True,
    ) -> list[StockPrice]:
        """
        Get stock price history from database.

        Args:
            symbol: Stock ticker symbol
            days: Number of days to fetch
            include_usd: Include USD conversion (requires exchange rate sync)

        Returns:
            List of StockPrice records
        """
        stock = await self.get_stock_by_symbol(symbol)
        if not stock:
            raise StockNotFoundError(f"Stock not found: {symbol}")

        start_date = date.today() - timedelta(days=days)

        query = (
            select(StockPrice)
            .where(
                and_(
                    StockPrice.stock_id == stock.id,
                    StockPrice.price_date >= start_date,
                )
            )
            .order_by(StockPrice.price_date.desc())
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_latest_price(
        self,
        symbol: str,
    ) -> StockPrice | None:
        """
        Get the most recent price from database.

        Args:
            symbol: Stock ticker symbol

        Returns:
            StockPrice or None if no data
        """
        stock = await self.get_stock_by_symbol(symbol)
        if not stock:
            return None

        query = (
            select(StockPrice)
            .where(StockPrice.stock_id == stock.id)
            .order_by(StockPrice.price_date.desc())
            .limit(1)
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()


# Factory function for dependency injection
async def get_stock_service(db: AsyncSession) -> StockDataService:
    """Create StockDataService instance"""
    return StockDataService(db)
