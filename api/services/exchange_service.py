"""
Exchange Rate Data Collection Service

Collects USD/KRW exchange rate data from multiple sources:
1. yfinance (Yahoo Finance) - Primary source
2. Korea Eximbank API - Secondary/backup source

Implements Redis caching with 1-minute TTL for real-time rate,
and stores historical data in PostgreSQL.
"""

import logging
from datetime import datetime, timedelta, date
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
import yfinance as yf
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from api.core.redis import exchange_rate_cache, cache
from api.models.exchange import ExchangeRate

logger = logging.getLogger(__name__)

# Constants
CACHE_TTL_REALTIME = 60  # 1 minute for real-time rate
CACHE_TTL_DAILY = 300  # 5 minutes for daily rate
USD_KRW_SYMBOL = "USDKRW=X"  # Yahoo Finance symbol for USD/KRW
CURRENCY_PAIR = "USD/KRW"


class ExchangeRateServiceError(Exception):
    """Base exception for exchange rate service"""
    pass


class ExchangeRateFetchError(ExchangeRateServiceError):
    """Failed to fetch exchange rate from any source"""
    pass


class ExchangeRateService:
    """
    Service for collecting and managing exchange rate data.

    Features:
    - Fetches real-time rates from yfinance or Eximbank API
    - Caches rates in Redis (1-minute TTL)
    - Stores historical rates in PostgreSQL
    - Provides rate history for charts
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client for API calls"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client"""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    # =========================================================================
    # Real-time Rate Fetching
    # =========================================================================

    async def get_current_rate(self, force_refresh: bool = False) -> dict[str, Any]:
        """
        Get current USD/KRW exchange rate with Redis caching.

        Args:
            force_refresh: If True, bypass cache and fetch fresh data

        Returns:
            dict with rate, source, and timestamp
        """
        # Check Redis cache first (unless force refresh)
        if not force_refresh:
            cached = await exchange_rate_cache.get_realtime()
            if cached:
                logger.debug("Exchange rate retrieved from cache")
                return cached

        # Fetch from external source
        rate_data = await self._fetch_rate_from_sources()

        # Update Redis cache
        await exchange_rate_cache.set_realtime(
            rate=Decimal(rate_data["rate"]),
            source=rate_data["source"]
        )

        # Also add to minute data for historical tracking
        await exchange_rate_cache.add_minute_data(
            rate=Decimal(rate_data["rate"]),
            timestamp=datetime.now()
        )

        logger.info(f"Exchange rate fetched and cached: {rate_data['rate']} from {rate_data['source']}")
        return rate_data

    async def _fetch_rate_from_sources(self) -> dict[str, Any]:
        """
        Try to fetch rate from multiple sources in order of preference.

        Returns:
            dict with rate, source, and timestamp
        """
        errors = []

        # Try yfinance first (more reliable for real-time)
        try:
            return await self._fetch_from_yfinance()
        except Exception as e:
            errors.append(f"yfinance: {str(e)}")
            logger.warning(f"Failed to fetch from yfinance: {e}")

        # Try Eximbank API as backup
        try:
            return await self._fetch_from_eximbank()
        except Exception as e:
            errors.append(f"eximbank: {str(e)}")
            logger.warning(f"Failed to fetch from Eximbank: {e}")

        # All sources failed
        raise ExchangeRateFetchError(
            f"Failed to fetch exchange rate from all sources: {'; '.join(errors)}"
        )

    async def _fetch_from_yfinance(self) -> dict[str, Any]:
        """
        Fetch real-time USD/KRW rate from Yahoo Finance.

        Returns:
            dict with rate, source, and timestamp
        """
        try:
            ticker = yf.Ticker(USD_KRW_SYMBOL)

            # Get current price (fast info)
            info = ticker.fast_info
            current_price = info.last_price if hasattr(info, 'last_price') else None

            if current_price is None:
                # Fallback to history
                hist = ticker.history(period="1d", interval="1m")
                if hist.empty:
                    raise ValueError("No data returned from yfinance")
                current_price = float(hist['Close'].iloc[-1])

            return {
                "rate": str(round(current_price, 4)),
                "currency_pair": CURRENCY_PAIR,
                "source": "yfinance",
                "updated_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"yfinance fetch error: {e}")
            raise

    async def _fetch_from_eximbank(self) -> dict[str, Any]:
        """
        Fetch USD/KRW rate from Korea Eximbank Open API.

        Note: Eximbank API returns daily rates, not real-time.
        Rate updates at around 11:00 AM KST on business days.

        API: https://www.koreaexim.go.kr/site/program/financial/exchangeJSON

        Returns:
            dict with rate, source, and timestamp
        """
        # Eximbank API endpoint (public, no auth required for basic usage)
        url = "https://www.koreaexim.go.kr/site/program/financial/exchangeJSON"

        today = date.today()
        params = {
            "authkey": "",  # Empty for public access (limited calls)
            "searchdate": today.strftime("%Y%m%d"),
            "data": "AP01",  # Exchange rate data type
        }

        try:
            client = await self._get_http_client()
            response = await client.get(url, params=params)
            response.raise_for_status()

            data = response.json()

            if not data or data == [{"RESULT": 4}]:
                # Try previous business day if today's data not available
                yesterday = today - timedelta(days=1)
                params["searchdate"] = yesterday.strftime("%Y%m%d")
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()

            if not data:
                raise ValueError("No data returned from Eximbank API")

            # Find USD rate
            usd_rate = None
            for item in data:
                if item.get("cur_unit") == "USD":
                    # Remove commas and convert to float
                    rate_str = item.get("deal_bas_r", "").replace(",", "")
                    if rate_str:
                        usd_rate = float(rate_str)
                        break

            if usd_rate is None:
                raise ValueError("USD rate not found in Eximbank response")

            return {
                "rate": str(round(usd_rate, 4)),
                "currency_pair": CURRENCY_PAIR,
                "source": "eximbank",
                "updated_at": datetime.now().isoformat(),
            }
        except httpx.HTTPError as e:
            logger.error(f"Eximbank API HTTP error: {e}")
            raise
        except (KeyError, ValueError) as e:
            logger.error(f"Eximbank API parse error: {e}")
            raise

    # =========================================================================
    # Historical Data Management
    # =========================================================================

    async def save_rate_to_db(
        self,
        rate: Decimal,
        rate_date: datetime | None = None,
        source: str = "unknown",
    ) -> ExchangeRate:
        """
        Save exchange rate to database.
        Uses upsert to handle duplicate dates.

        Args:
            rate: Exchange rate value
            rate_date: Date/time of the rate (defaults to now)
            source: Data source identifier

        Returns:
            ExchangeRate model instance
        """
        if rate_date is None:
            rate_date = datetime.now()

        stmt = insert(ExchangeRate).values(
            currency_pair=CURRENCY_PAIR,
            rate=rate,
            rate_date=rate_date,
            source=source,
        ).on_conflict_do_update(
            constraint="uq_exchange_rates_pair_date",
            set_={
                "rate": rate,
                "source": source,
            }
        ).returning(ExchangeRate)

        result = await self.db.execute(stmt)
        await self.db.commit()

        return result.scalar_one()

    async def fetch_and_save_current_rate(self) -> ExchangeRate:
        """
        Fetch current rate from external source and save to database.

        Returns:
            ExchangeRate model instance
        """
        rate_data = await self._fetch_rate_from_sources()

        exchange_rate = await self.save_rate_to_db(
            rate=Decimal(rate_data["rate"]),
            rate_date=datetime.now(),
            source=rate_data["source"],
        )

        # Update cache
        await exchange_rate_cache.set_realtime(
            rate=Decimal(rate_data["rate"]),
            source=rate_data["source"]
        )

        # Clear history cache to reflect new data
        await cache.delete("exchange:usd_krw:current")

        return exchange_rate

    async def fetch_historical_rates(
        self,
        start_date: date,
        end_date: date | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch historical exchange rates from yfinance.

        Args:
            start_date: Start date for history
            end_date: End date for history (defaults to today)

        Returns:
            List of rate data dictionaries
        """
        if end_date is None:
            end_date = date.today()

        try:
            ticker = yf.Ticker(USD_KRW_SYMBOL)
            hist = ticker.history(
                start=start_date.isoformat(),
                end=(end_date + timedelta(days=1)).isoformat(),
                interval="1d",
            )

            if hist.empty:
                logger.warning(f"No historical data for {start_date} to {end_date}")
                return []

            rates = []
            for idx, row in hist.iterrows():
                rate_date = idx.to_pydatetime()
                rates.append({
                    "rate": str(round(row["Close"], 4)),
                    "rate_date": rate_date.isoformat(),
                    "source": "yfinance",
                })

            return rates
        except Exception as e:
            logger.error(f"Failed to fetch historical rates: {e}")
            raise ExchangeRateFetchError(f"Failed to fetch historical rates: {e}")

    async def sync_historical_rates(
        self,
        days: int = 30,
    ) -> int:
        """
        Sync historical exchange rates to database.
        Fills gaps in historical data.

        Args:
            days: Number of days to sync (default 30)

        Returns:
            Number of records inserted/updated
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        # Fetch historical data
        historical_data = await self.fetch_historical_rates(start_date, end_date)

        if not historical_data:
            return 0

        count = 0
        for data in historical_data:
            try:
                rate_date = datetime.fromisoformat(data["rate_date"])
                await self.save_rate_to_db(
                    rate=Decimal(data["rate"]),
                    rate_date=rate_date,
                    source=data["source"],
                )
                count += 1
            except Exception as e:
                logger.warning(f"Failed to save rate for {data['rate_date']}: {e}")

        logger.info(f"Synced {count} historical exchange rates")
        return count

    async def get_rate_history(
        self,
        days: int = 30,
    ) -> list[ExchangeRate]:
        """
        Get exchange rate history from database.

        Args:
            days: Number of days to fetch

        Returns:
            List of ExchangeRate records
        """
        start_date = datetime.now() - timedelta(days=days)

        query = (
            select(ExchangeRate)
            .where(
                and_(
                    ExchangeRate.currency_pair == CURRENCY_PAIR,
                    ExchangeRate.rate_date >= start_date,
                )
            )
            .order_by(ExchangeRate.rate_date.desc())
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def get_latest_db_rate(self) -> ExchangeRate | None:
        """
        Get the latest exchange rate from database.

        Returns:
            ExchangeRate or None if no data
        """
        query = (
            select(ExchangeRate)
            .where(ExchangeRate.currency_pair == CURRENCY_PAIR)
            .order_by(ExchangeRate.rate_date.desc())
            .limit(1)
        )

        result = await self.db.execute(query)
        return result.scalar_one_or_none()

    async def calculate_rate_change(
        self,
        current_rate: Decimal,
    ) -> tuple[Decimal | None, Decimal | None]:
        """
        Calculate rate change from previous day.

        Args:
            current_rate: Current exchange rate

        Returns:
            Tuple of (change, change_percent) or (None, None)
        """
        # Get previous day's rate
        yesterday = datetime.now() - timedelta(days=1)

        query = (
            select(ExchangeRate)
            .where(
                and_(
                    ExchangeRate.currency_pair == CURRENCY_PAIR,
                    ExchangeRate.rate_date < datetime.now(),
                )
            )
            .order_by(ExchangeRate.rate_date.desc())
            .limit(1)
        )

        result = await self.db.execute(query)
        prev_rate = result.scalar_one_or_none()

        if prev_rate is None:
            return None, None

        change = current_rate - prev_rate.rate
        change_percent = (change / prev_rate.rate) * 100

        return round(change, 4), round(change_percent, 4)


# Factory function for dependency injection
async def get_exchange_service(db: AsyncSession) -> ExchangeRateService:
    """Create ExchangeRateService instance"""
    return ExchangeRateService(db)
