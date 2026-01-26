"""
Exchange Rate API Endpoints

Provides:
- Real-time USD/KRW exchange rate with Redis caching (1-minute TTL)
- Historical exchange rate data
- Currency conversion
- Data synchronization endpoints
"""

import logging
from datetime import datetime, date, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.redis import cache, exchange_rate_cache
from api.models.exchange import ExchangeRate
from api.schemas.common import APIResponse
from api.schemas.exchange import (
    ExchangeRateResponse,
    ExchangeRateRealtimeResponse,
    ExchangeRateSyncRequest,
    ExchangeRateSyncResponse,
    ConvertCurrencyResponse,
)
from api.services.exchange_service import (
    ExchangeRateService,
    ExchangeRateFetchError,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# =============================================================================
# Real-time Rate Endpoints
# =============================================================================


@router.get("/rate", response_model=APIResponse[ExchangeRateRealtimeResponse])
async def get_current_rate(
    force_refresh: bool = Query(
        False,
        description="Bypass cache and fetch fresh data"
    ),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ExchangeRateRealtimeResponse]:
    """
    Get current USD/KRW exchange rate.

    Returns real-time exchange rate with 1-minute Redis caching.
    Data sources: yfinance (primary), Eximbank API (backup).
    """
    service = ExchangeRateService(db)

    try:
        # Get real-time rate (cached or fresh)
        rate_data = await service.get_current_rate(force_refresh=force_refresh)

        # Calculate change from previous rate
        current_rate = Decimal(rate_data["rate"])
        change, change_percent = await service.calculate_rate_change(current_rate)

        response = ExchangeRateRealtimeResponse(
            rate=current_rate,
            currency_pair=rate_data.get("currency_pair", "USD/KRW"),
            source=rate_data.get("source", "unknown"),
            updated_at=datetime.fromisoformat(rate_data["updated_at"]),
            change=change,
            change_percent=change_percent,
        )

        return APIResponse(
            success=True,
            message="Exchange rate retrieved successfully",
            data=response,
        )
    except ExchangeRateFetchError as e:
        logger.error(f"Failed to fetch exchange rate: {e}")

        # Try to return cached/DB data as fallback
        cached = await exchange_rate_cache.get_realtime()
        if cached:
            return APIResponse(
                success=True,
                message="Using cached exchange rate (fetch failed)",
                data=ExchangeRateRealtimeResponse(
                    rate=Decimal(cached["rate"]),
                    currency_pair=cached.get("currency_pair", "USD/KRW"),
                    source=cached.get("source", "cache"),
                    updated_at=datetime.fromisoformat(cached["updated_at"]),
                ),
            )

        # Try database
        latest = await service.get_latest_db_rate()
        if latest:
            return APIResponse(
                success=True,
                message="Using database exchange rate (fetch failed)",
                data=ExchangeRateRealtimeResponse(
                    rate=latest.rate,
                    currency_pair=latest.currency_pair,
                    source=latest.source or "database",
                    updated_at=latest.rate_date,
                ),
            )

        return APIResponse(
            success=False,
            message=f"Failed to fetch exchange rate: {str(e)}",
            data=None,
        )
    finally:
        await service.close()


@router.get("/rate/cached", response_model=APIResponse[ExchangeRateRealtimeResponse | None])
async def get_cached_rate() -> APIResponse[ExchangeRateRealtimeResponse | None]:
    """
    Get cached exchange rate without fetching from external source.

    Returns cached rate if available, null otherwise.
    Useful for quick checks without making external API calls.
    """
    cached = await exchange_rate_cache.get_realtime()

    if cached:
        return APIResponse(
            success=True,
            message="Cached exchange rate retrieved",
            data=ExchangeRateRealtimeResponse(
                rate=Decimal(cached["rate"]),
                currency_pair=cached.get("currency_pair", "USD/KRW"),
                source=cached.get("source", "cache"),
                updated_at=datetime.fromisoformat(cached["updated_at"]),
            ),
        )

    return APIResponse(
        success=False,
        message="No cached exchange rate available",
        data=None,
    )


# =============================================================================
# History Endpoints
# =============================================================================


@router.get("/history", response_model=APIResponse[list[ExchangeRateResponse]])
async def get_rate_history(
    days: int = Query(30, ge=1, le=365, description="Number of days to fetch"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[ExchangeRateResponse]]:
    """
    Get exchange rate history from database.

    Returns daily exchange rates for the specified number of days.
    """
    service = ExchangeRateService(db)

    try:
        rates = await service.get_rate_history(days=days)

        response_data = []
        prev_rate = None

        # Calculate changes (rates are in descending order)
        for rate in reversed(rates):
            change = None
            change_percent = None

            if prev_rate is not None:
                change = rate.rate - prev_rate
                if prev_rate != 0:
                    change_percent = (change / prev_rate) * 100

            response_data.append(
                ExchangeRateResponse(
                    id=rate.id,
                    currency_pair=rate.currency_pair,
                    rate=rate.rate,
                    rate_date=rate.rate_date,
                    source=rate.source,
                    change=round(change, 4) if change else None,
                    change_percent=round(change_percent, 4) if change_percent else None,
                )
            )
            prev_rate = rate.rate

        # Reverse back to descending order (most recent first)
        response_data.reverse()

        return APIResponse(
            success=True,
            message=f"Retrieved {len(response_data)} exchange rate records",
            data=response_data,
        )
    finally:
        await service.close()


# =============================================================================
# Conversion Endpoints
# =============================================================================


@router.get("/convert", response_model=APIResponse[ConvertCurrencyResponse])
async def convert_currency(
    amount: Decimal = Query(..., gt=0, description="Amount to convert"),
    from_currency: str = Query("KRW", description="Source currency"),
    to_currency: str = Query("USD", description="Target currency"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ConvertCurrencyResponse]:
    """
    Convert amount between KRW and USD.

    Uses the current cached exchange rate for conversion.
    """
    service = ExchangeRateService(db)

    try:
        # Get current rate
        rate_data = await service.get_current_rate()
        rate = Decimal(rate_data["rate"])

        from_curr = from_currency.upper()
        to_curr = to_currency.upper()

        if from_curr == to_curr:
            converted = amount
        elif from_curr == "KRW" and to_curr == "USD":
            converted = amount / rate
        elif from_curr == "USD" and to_curr == "KRW":
            converted = amount * rate
        else:
            return APIResponse(
                success=False,
                message="Only KRW <-> USD conversion is supported",
                data=None,
            )

        return APIResponse(
            success=True,
            message="Currency conversion successful",
            data=ConvertCurrencyResponse(
                original_amount=amount,
                original_currency=from_curr,
                converted_amount=round(converted, 4),
                converted_currency=to_curr,
                exchange_rate=rate,
                rate_date=datetime.fromisoformat(rate_data["updated_at"]),
            ),
        )
    except ExchangeRateFetchError as e:
        return APIResponse(
            success=False,
            message=f"Failed to get exchange rate: {str(e)}",
            data=None,
        )
    finally:
        await service.close()


# =============================================================================
# Sync Endpoints (for data collection)
# =============================================================================


@router.post("/sync", response_model=APIResponse[ExchangeRateSyncResponse])
async def sync_current_rate(
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ExchangeRateSyncResponse]:
    """
    Fetch current exchange rate and save to database.

    This endpoint fetches the current rate from external sources,
    caches it in Redis, and persists it to the database.
    """
    service = ExchangeRateService(db)

    try:
        exchange_rate = await service.fetch_and_save_current_rate()

        return APIResponse(
            success=True,
            message="Exchange rate synced successfully",
            data=ExchangeRateSyncResponse(
                synced_count=1,
                start_date=exchange_rate.rate_date.date(),
                end_date=exchange_rate.rate_date.date(),
                source=exchange_rate.source or "unknown",
            ),
        )
    except ExchangeRateFetchError as e:
        logger.error(f"Failed to sync exchange rate: {e}")
        return APIResponse(
            success=False,
            message=f"Failed to sync exchange rate: {str(e)}",
            data=None,
        )
    finally:
        await service.close()


@router.post("/sync/historical", response_model=APIResponse[ExchangeRateSyncResponse])
async def sync_historical_rates(
    request: ExchangeRateSyncRequest = None,
    days: int = Query(30, ge=1, le=365, description="Number of days to sync"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ExchangeRateSyncResponse]:
    """
    Sync historical exchange rates to database.

    Fetches historical rates from yfinance and stores them in the database.
    Uses upsert to handle existing records.
    """
    # Use request body if provided, otherwise use query param
    sync_days = request.days if request else days

    service = ExchangeRateService(db)

    try:
        end_date = date.today()
        start_date = end_date - timedelta(days=sync_days)

        synced_count = await service.sync_historical_rates(days=sync_days)

        return APIResponse(
            success=True,
            message=f"Synced {synced_count} historical exchange rates",
            data=ExchangeRateSyncResponse(
                synced_count=synced_count,
                start_date=start_date,
                end_date=end_date,
                source="yfinance",
            ),
        )
    except ExchangeRateFetchError as e:
        logger.error(f"Failed to sync historical rates: {e}")
        return APIResponse(
            success=False,
            message=f"Failed to sync historical rates: {str(e)}",
            data=None,
        )
    finally:
        await service.close()


@router.delete("/cache", response_model=APIResponse[dict])
async def clear_exchange_cache() -> APIResponse[dict]:
    """
    Clear exchange rate cache.

    Removes cached real-time rate from Redis.
    Useful for forcing a fresh fetch on next request.
    """
    # Clear real-time cache
    await cache.delete("exchange:usd_krw:current")

    # Clear the specialized cache key
    from api.core.redis import get_redis
    client = await get_redis()
    await client.delete("krxusd:exchange:realtime")

    return APIResponse(
        success=True,
        message="Exchange rate cache cleared",
        data={"cleared": True},
    )
