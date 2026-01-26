from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.redis import cache
from api.models.exchange import ExchangeRate
from api.schemas.common import APIResponse
from api.schemas.exchange import ExchangeRateResponse

router = APIRouter()


@router.get("/rate")
async def get_current_rate(
    db: AsyncSession = Depends(get_db),
) -> APIResponse[ExchangeRateResponse]:
    """
    Get current USD/KRW exchange rate
    """
    # Try to get from cache first
    cached_rate = await cache.get("exchange:usd_krw:current")
    if cached_rate:
        return APIResponse(data=ExchangeRateResponse(**cached_rate))

    # Get from database
    query = (
        select(ExchangeRate)
        .where(ExchangeRate.currency_pair == "USD/KRW")
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
    )
    result = await db.execute(query)
    rate = result.scalar_one_or_none()

    if rate:
        response_data = ExchangeRateResponse.model_validate(rate)
        # Cache for 1 minute
        await cache.set(
            "exchange:usd_krw:current",
            response_data.model_dump(mode="json"),
            ttl=60,
        )
        return APIResponse(data=response_data)

    # Return placeholder if no data
    return APIResponse(
        success=False,
        message="No exchange rate data available",
        data=None,
    )


@router.get("/history")
async def get_rate_history(
    days: int = Query(30, ge=1, le=365, description="Number of days to fetch"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[ExchangeRateResponse]]:
    """
    Get exchange rate history
    """
    query = (
        select(ExchangeRate)
        .where(ExchangeRate.currency_pair == "USD/KRW")
        .order_by(ExchangeRate.rate_date.desc())
        .limit(days)
    )
    result = await db.execute(query)
    rates = result.scalars().all()

    return APIResponse(
        data=[ExchangeRateResponse.model_validate(r) for r in rates]
    )


@router.get("/convert")
async def convert_currency(
    amount: Decimal = Query(..., description="Amount to convert"),
    from_currency: str = Query("KRW", description="Source currency"),
    to_currency: str = Query("USD", description="Target currency"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[dict]:
    """
    Convert amount between KRW and USD
    """
    # Get current rate
    query = (
        select(ExchangeRate)
        .where(ExchangeRate.currency_pair == "USD/KRW")
        .order_by(ExchangeRate.rate_date.desc())
        .limit(1)
    )
    result = await db.execute(query)
    rate = result.scalar_one_or_none()

    if not rate:
        return APIResponse(
            success=False,
            message="No exchange rate data available",
            data=None,
        )

    from_currency = from_currency.upper()
    to_currency = to_currency.upper()

    if from_currency == "KRW" and to_currency == "USD":
        converted = amount / rate.rate
    elif from_currency == "USD" and to_currency == "KRW":
        converted = amount * rate.rate
    else:
        return APIResponse(
            success=False,
            message="Only KRW <-> USD conversion is supported",
            data=None,
        )

    return APIResponse(
        data={
            "original_amount": float(amount),
            "original_currency": from_currency,
            "converted_amount": round(float(converted), 4),
            "converted_currency": to_currency,
            "exchange_rate": float(rate.rate),
            "rate_date": rate.rate_date.isoformat(),
        }
    )
