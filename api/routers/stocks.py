from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.models.stock import Stock, StockPrice
from api.schemas.common import APIResponse, PaginatedResponse
from api.schemas.stock import StockResponse, StockPriceResponse, StockDetailResponse

router = APIRouter()


@router.get("")
async def list_stocks(
    market: str | None = Query(None, description="Filter by market (KOSPI/KOSDAQ)"),
    search: str | None = Query(None, description="Search by name or symbol"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedResponse[StockResponse]]:
    """
    List all stocks with optional filtering and pagination
    """
    query = select(Stock)

    if market:
        query = query.where(Stock.market == market.upper())

    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Stock.name.ilike(search_term)) | (Stock.symbol.ilike(search_term))
        )

    # Count total
    count_query = select(Stock.id)
    if market:
        count_query = count_query.where(Stock.market == market.upper())
    if search:
        count_query = count_query.where(
            (Stock.name.ilike(search_term)) | (Stock.symbol.ilike(search_term))
        )

    result = await db.execute(count_query)
    total = len(result.all())

    # Paginate
    offset = (page - 1) * size
    query = query.offset(offset).limit(size)

    result = await db.execute(query)
    stocks = result.scalars().all()

    pages = (total + size - 1) // size

    return APIResponse(
        data=PaginatedResponse(
            items=[StockResponse.model_validate(s) for s in stocks],
            total=total,
            page=page,
            size=size,
            pages=pages,
        )
    )


@router.get("/{symbol}")
async def get_stock(
    symbol: str,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[StockDetailResponse]:
    """
    Get detailed stock information by symbol
    """
    query = select(Stock).where(Stock.symbol == symbol.upper())
    result = await db.execute(query)
    stock = result.scalar_one_or_none()

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    # Get latest price
    price_query = (
        select(StockPrice)
        .where(StockPrice.stock_id == stock.id)
        .order_by(StockPrice.price_date.desc())
        .limit(1)
    )
    price_result = await db.execute(price_query)
    latest_price = price_result.scalar_one_or_none()

    stock_response = StockResponse.model_validate(stock)
    price_response = (
        StockPriceResponse.model_validate(latest_price) if latest_price else None
    )

    # Calculate market cap if we have price and shares
    market_cap_krw = None
    market_cap_usd = None
    if latest_price and stock.listed_shares:
        market_cap_krw = latest_price.close_price * stock.listed_shares
        if latest_price.exchange_rate:
            market_cap_usd = market_cap_krw / latest_price.exchange_rate

    return APIResponse(
        data=StockDetailResponse(
            stock=stock_response,
            current_price=price_response,
            market_cap_krw=market_cap_krw,
            market_cap_usd=market_cap_usd,
        )
    )


@router.get("/{symbol}/prices")
async def get_stock_prices(
    symbol: str,
    days: int = Query(30, ge=1, le=365, description="Number of days to fetch"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[StockPriceResponse]]:
    """
    Get historical prices for a stock
    """
    # First get the stock
    stock_query = select(Stock).where(Stock.symbol == symbol.upper())
    stock_result = await db.execute(stock_query)
    stock = stock_result.scalar_one_or_none()

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    # Get prices
    price_query = (
        select(StockPrice)
        .where(StockPrice.stock_id == stock.id)
        .order_by(StockPrice.price_date.desc())
        .limit(days)
    )
    result = await db.execute(price_query)
    prices = result.scalars().all()

    return APIResponse(
        data=[StockPriceResponse.model_validate(p) for p in prices]
    )
