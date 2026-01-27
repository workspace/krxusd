"""
Stock API Router

Provides endpoints for:
- Listing and searching stocks
- Getting stock details and historical prices
- Real-time price fetching with Redis caching
- Syncing historical data with Gap Filling strategy
"""

from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.database import get_db
from api.core.redis import stock_realtime_cache, cache
from api.models.stock import Stock, StockPrice, SyncStatus
from api.schemas.common import APIResponse, PaginatedResponse
from api.schemas.stock import (
    StockResponse,
    StockPriceResponse,
    StockDetailResponse,
    StockRealtimePriceResponse,
    StockRealtimeBatchRequest,
    StockRealtimeBatchResponse,
    StockSyncRequest,
    StockSyncResponse,
    StockBatchSyncRequest,
    StockBatchSyncResponse,
    SyncStatusResponse,
    DataSummaryResponse,
    SyncRangeInfo,
    GapAnalysisResponse,
    EnsureDataSyncedResponse,
)
from api.services.stock_service import (
    StockDataService,
    StockDataServiceError,
    StockNotFoundError,
    StockDataFetchError,
)
from api.services.scheduler_service import register_active_symbol

router = APIRouter()


# =========================================================================
# Stock Listing & Details
# =========================================================================


@router.get("")
async def list_stocks(
    market: str | None = Query(None, description="Filter by market (KOSPI/KOSDAQ)"),
    search: str | None = Query(None, description="Search by name or symbol"),
    is_active: bool = Query(True, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[PaginatedResponse[StockResponse]]:
    """
    List all stocks with optional filtering and pagination.

    - **market**: Filter by KOSPI, KOSDAQ, or KONEX
    - **search**: Search in stock name or symbol
    - **is_active**: Filter by active/inactive status
    - **page**: Page number (starts at 1)
    - **size**: Number of items per page (max 100)
    """
    query = select(Stock).where(Stock.is_active == is_active)

    if market:
        query = query.where(Stock.market == market.upper())

    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Stock.name.ilike(search_term)) | (Stock.symbol.ilike(search_term))
        )

    # Count total
    count_query = select(Stock.id).where(Stock.is_active == is_active)
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
    query = query.order_by(Stock.symbol).offset(offset).limit(size)

    result = await db.execute(query)
    stocks = result.scalars().all()

    pages = (total + size - 1) // size if total > 0 else 0

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
    Get detailed stock information by symbol.

    Returns stock master data along with the latest price and market cap.

    Note: This endpoint automatically registers the symbol for realtime updates.
    """
    query = select(Stock).where(Stock.symbol == symbol.upper())
    result = await db.execute(query)
    stock = result.scalar_one_or_none()

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    # Register symbol for realtime updates (scheduler will update this symbol)
    await register_active_symbol(symbol)

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
    Get historical prices for a stock.

    Returns OHLCV data with USD conversion for the specified number of days.
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


# =========================================================================
# Real-time Price Endpoints
# =========================================================================


@router.get("/{symbol}/realtime")
async def get_realtime_price(
    symbol: str,
    force_refresh: bool = Query(False, description="Bypass cache and fetch fresh data"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[StockRealtimePriceResponse]:
    """
    Get real-time stock price with Redis caching.

    - Returns cached data if available (2-minute TTL)
    - Fetches from external source if cache miss
    - Includes USD conversion using current exchange rate

    Sources: FinanceDataReader (primary), Yahoo Finance (backup)

    Note: This endpoint automatically registers the symbol for realtime updates.
    """
    # Register symbol for realtime updates
    await register_active_symbol(symbol)

    service = StockDataService(db)

    try:
        price_data = await service.get_realtime_price(
            symbol, force_refresh=force_refresh
        )

        return APIResponse(
            message="Real-time price fetched successfully",
            data=StockRealtimePriceResponse(
                symbol=price_data["symbol"],
                open_price=Decimal(price_data["open_price"]),
                high_price=Decimal(price_data["high_price"]),
                low_price=Decimal(price_data["low_price"]),
                close_price=Decimal(price_data["close_price"]),
                volume=price_data["volume"],
                change=Decimal(price_data["change"]),
                change_percent=Decimal(price_data["change_percent"]),
                close_price_usd=(
                    Decimal(price_data["close_price_usd"])
                    if price_data.get("close_price_usd")
                    else None
                ),
                exchange_rate=(
                    Decimal(price_data["exchange_rate"])
                    if price_data.get("exchange_rate")
                    else None
                ),
                price_date=price_data["price_date"],
                source=price_data["source"],
                updated_at=price_data["updated_at"],
            ),
        )
    except StockDataFetchError as e:
        raise HTTPException(status_code=503, detail=str(e))
    finally:
        await service.close()


@router.get("/{symbol}/realtime/cached")
async def get_cached_price(
    symbol: str,
) -> APIResponse[StockRealtimePriceResponse | None]:
    """
    Get cached real-time price only (no external fetch).

    Returns the cached price if available, None otherwise.
    Useful for checking cache status without triggering an external API call.
    """
    cached = await stock_realtime_cache.get(symbol.upper())

    if cached is None:
        return APIResponse(
            success=True,
            message="No cached data available",
            data=None,
        )

    return APIResponse(
        message="Cached price retrieved",
        data=StockRealtimePriceResponse(
            symbol=cached["symbol"],
            open_price=Decimal(cached["open_price"]),
            high_price=Decimal(cached["high_price"]),
            low_price=Decimal(cached["low_price"]),
            close_price=Decimal(cached["close_price"]),
            volume=cached["volume"],
            change=Decimal(cached["change"]),
            change_percent=Decimal(cached["change_percent"]),
            close_price_usd=(
                Decimal(cached["close_price_usd"])
                if cached.get("close_price_usd")
                else None
            ),
            exchange_rate=(
                Decimal(cached["exchange_rate"])
                if cached.get("exchange_rate")
                else None
            ),
            price_date=cached["price_date"],
            source=cached["source"],
            updated_at=cached["updated_at"],
        ),
    )


@router.post("/realtime/batch")
async def get_realtime_prices_batch(
    request: StockRealtimeBatchRequest,
    force_refresh: bool = Query(False, description="Bypass cache for all symbols"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[StockRealtimeBatchResponse]:
    """
    Get real-time prices for multiple stocks in one request.

    - Checks cache for all symbols first
    - Fetches only missing symbols from external source
    - Returns None for symbols that failed to fetch

    Maximum 50 symbols per request.
    """
    service = StockDataService(db)

    try:
        results = await service.get_realtime_prices_batch(
            request.symbols, force_refresh=force_refresh
        )

        prices: dict[str, StockRealtimePriceResponse | None] = {}
        success_count = 0
        failed_count = 0

        for symbol, data in results.items():
            if data:
                prices[symbol] = StockRealtimePriceResponse(
                    symbol=data["symbol"],
                    open_price=Decimal(data["open_price"]),
                    high_price=Decimal(data["high_price"]),
                    low_price=Decimal(data["low_price"]),
                    close_price=Decimal(data["close_price"]),
                    volume=data["volume"],
                    change=Decimal(data["change"]),
                    change_percent=Decimal(data["change_percent"]),
                    close_price_usd=(
                        Decimal(data["close_price_usd"])
                        if data.get("close_price_usd")
                        else None
                    ),
                    exchange_rate=(
                        Decimal(data["exchange_rate"])
                        if data.get("exchange_rate")
                        else None
                    ),
                    price_date=data["price_date"],
                    source=data["source"],
                    updated_at=data["updated_at"],
                )
                success_count += 1
            else:
                prices[symbol] = None
                failed_count += 1

        return APIResponse(
            message=f"Fetched {success_count} prices, {failed_count} failed",
            data=StockRealtimeBatchResponse(
                prices=prices,
                success_count=success_count,
                failed_count=failed_count,
            ),
        )
    finally:
        await service.close()


# =========================================================================
# Data Sync Endpoints (Gap Filling Strategy)
# =========================================================================


@router.post("/{symbol}/sync")
async def sync_stock_prices(
    symbol: str,
    request: StockSyncRequest = StockSyncRequest(),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[StockSyncResponse]:
    """
    Sync historical prices for a stock using Gap Filling strategy.

    **Gap Filling Cases:**
    - **Case A (no_data)**: No data exists - full collection from start_date
    - **Case B (gap_detected)**: Gap in data - collect only missing dates
    - **Case C (up_to_date)**: Data is current - no action needed

    The strategy automatically determines the optimal sync range based on
    existing data in the database.

    Use `force_full_sync=true` to override gap analysis and do a complete resync.
    """
    service = StockDataService(db)

    try:
        # Calculate start date based on days parameter
        from datetime import timedelta
        start_date = date.today() - timedelta(days=request.days)

        result = await service.sync_stock_prices(
            symbol=symbol,
            start_date=start_date if request.force_full_sync else None,
            force_full_sync=request.force_full_sync,
        )

        return APIResponse(
            message=f"Sync completed: {result['sync_case']}",
            data=StockSyncResponse(
                symbol=result["symbol"],
                sync_case=result["sync_case"],
                synced_count=result["synced_count"],
                start_date=result.get("start_date"),
                end_date=result.get("end_date"),
                source=result.get("source"),
                message=result.get("message"),
            ),
        )
    except StockDataFetchError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")
    finally:
        await service.close()


@router.post("/sync/batch")
async def sync_stocks_batch(
    request: StockBatchSyncRequest,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[StockBatchSyncResponse]:
    """
    Sync historical prices for multiple stocks.

    Processes each stock independently, collecting results.
    Failures for individual stocks don't stop the batch operation.

    Maximum 100 symbols per request.
    """
    service = StockDataService(db)
    results: list[StockSyncResponse] = []
    success_count = 0
    failed_count = 0

    try:
        from datetime import timedelta
        start_date = date.today() - timedelta(days=request.days)

        for symbol in request.symbols:
            try:
                result = await service.sync_stock_prices(
                    symbol=symbol,
                    start_date=start_date if request.force_full_sync else None,
                    force_full_sync=request.force_full_sync,
                )
                results.append(
                    StockSyncResponse(
                        symbol=result["symbol"],
                        sync_case=result["sync_case"],
                        synced_count=result["synced_count"],
                        start_date=result.get("start_date"),
                        end_date=result.get("end_date"),
                        source=result.get("source"),
                        message=result.get("message"),
                    )
                )
                success_count += 1
            except Exception as e:
                results.append(
                    StockSyncResponse(
                        symbol=symbol,
                        sync_case="failed",
                        synced_count=0,
                        message=str(e)[:200],
                    )
                )
                failed_count += 1

        return APIResponse(
            message=f"Batch sync completed: {success_count} success, {failed_count} failed",
            data=StockBatchSyncResponse(
                total_requested=len(request.symbols),
                success_count=success_count,
                failed_count=failed_count,
                results=results,
            ),
        )
    finally:
        await service.close()


@router.get("/{symbol}/sync/status")
async def get_sync_status(
    symbol: str,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[SyncStatusResponse | None]:
    """
    Get sync status for a stock.

    Returns the current synchronization status including:
    - Last sync date
    - Sync status (pending, syncing, completed, failed)
    - Error message if failed
    """
    # Get stock first
    stock_query = select(Stock).where(Stock.symbol == symbol.upper())
    stock_result = await db.execute(stock_query)
    stock = stock_result.scalar_one_or_none()

    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

    # Get sync status
    status_query = (
        select(SyncStatus)
        .where(SyncStatus.stock_id == stock.id)
        .where(SyncStatus.data_type == "daily_price")
    )
    status_result = await db.execute(status_query)
    sync_status = status_result.scalar_one_or_none()

    if not sync_status:
        return APIResponse(
            message="No sync status found",
            data=None,
        )

    return APIResponse(
        data=SyncStatusResponse.model_validate(sync_status),
    )


# =========================================================================
# Gap Filling Endpoints (Data Sync on Page Access)
# =========================================================================


@router.get("/{symbol}/gaps")
async def analyze_gaps(
    symbol: str,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[GapAnalysisResponse]:
    """
    Analyze data gaps for a stock without performing sync.

    This endpoint performs a dry-run analysis to check:
    - Whether data exists in the database
    - What sync case applies (no_data, gap_detected, up_to_date)
    - What date range needs to be synced
    - Estimated number of records to sync

    Use this to understand the gap status before triggering a sync.
    """
    service = StockDataService(db)

    try:
        result = await service.check_and_report_gaps(symbol)

        if not result.get("exists"):
            return APIResponse(
                message="Stock not found",
                data=GapAnalysisResponse(
                    symbol=symbol.upper(),
                    exists=False,
                    message=result.get("message", "Stock not found in database"),
                ),
            )

        # Build data summary if available
        data_summary = None
        if result.get("data_summary"):
            ds = result["data_summary"]
            data_summary = DataSummaryResponse(
                symbol=ds["symbol"],
                stock_id=ds["stock_id"],
                has_data=ds["has_data"],
                first_date=ds.get("first_date"),
                last_date=ds.get("last_date"),
                count=ds.get("count", 0),
                listing_date=ds.get("listing_date"),
            )

        # Build sync range if applicable
        sync_range = None
        if result.get("sync_range"):
            sr = result["sync_range"]
            sync_range = SyncRangeInfo(
                start_date=sr.get("start_date"),
                end_date=sr.get("end_date"),
            )

        return APIResponse(
            message=f"Gap analysis completed: {result.get('sync_case', 'unknown')}",
            data=GapAnalysisResponse(
                symbol=symbol.upper(),
                exists=True,
                sync_case=result.get("sync_case"),
                case_description=result.get("case_description"),
                needs_sync=result.get("needs_sync", False),
                data_summary=data_summary,
                sync_range=sync_range,
                estimated_records=result.get("estimated_records"),
            ),
        )
    finally:
        await service.close()


@router.post("/{symbol}/ensure-synced")
async def ensure_data_synced(
    symbol: str,
    auto_sync: bool = Query(True, description="Automatically sync if gap detected"),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[EnsureDataSyncedResponse]:
    """
    Ensure stock price data is synced (Gap Filling on page access).

    This endpoint implements the Gap Filling strategy triggered when
    a user accesses the stock detail page:

    **Gap Filling Cases:**
    - **Case A (no_data)**: No data exists → Full collection from listing_date to yesterday
    - **Case B (gap_detected)**: Last saved date < yesterday → Append missing dates
    - **Case C (up_to_date)**: Last saved date >= yesterday → No action

    If `auto_sync=true` (default), the sync is performed automatically
    for Case A and Case B. Set to `false` to only check status without syncing.

    This is the main entry point for frontend to ensure data is available
    when displaying stock detail pages.
    """
    service = StockDataService(db)

    try:
        result = await service.ensure_data_synced(symbol, auto_sync=auto_sync)

        # Build data summary
        data_summary = None
        if result.get("data_summary"):
            ds = result["data_summary"]
            data_summary = DataSummaryResponse(
                symbol=ds["symbol"],
                stock_id=ds["stock_id"],
                has_data=ds["has_data"],
                first_date=ds.get("first_date"),
                last_date=ds.get("last_date"),
                count=ds.get("count", 0),
                listing_date=ds.get("listing_date"),
            )

        # Build sync range
        sync_range = None
        if result.get("sync_range"):
            sr = result["sync_range"]
            sync_range = SyncRangeInfo(
                start_date=sr.get("start_date"),
                end_date=sr.get("end_date"),
            )

        # Build sync result if sync was performed
        sync_result = None
        if result.get("sync_result"):
            sr = result["sync_result"]
            sync_result = StockSyncResponse(
                symbol=sr["symbol"],
                sync_case=sr["sync_case"],
                synced_count=sr["synced_count"],
                start_date=sr.get("start_date"),
                end_date=sr.get("end_date"),
                source=sr.get("source"),
                message=sr.get("message"),
            )

        return APIResponse(
            message=result.get("message", "Sync check completed"),
            data=EnsureDataSyncedResponse(
                symbol=symbol.upper(),
                sync_case=result["sync_case"],
                needs_sync=result["needs_sync"],
                synced=result.get("synced", False),
                data_summary=data_summary,
                sync_range=sync_range,
                sync_result=sync_result,
                sync_error=result.get("sync_error"),
                message=result.get("message"),
            ),
        )
    except StockDataFetchError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ensure sync failed: {str(e)}")
    finally:
        await service.close()


@router.get("/{symbol}/data-summary")
async def get_data_summary(
    symbol: str,
    db: AsyncSession = Depends(get_db),
) -> APIResponse[DataSummaryResponse | None]:
    """
    Get a summary of stored price data for a stock.

    Returns:
    - First and last price dates (first_date = earliest, last_date = last_saved_date)
    - Total count of price records
    - Stock's listing date (for reference)

    This is useful for understanding what data is currently available
    before deciding whether to sync.
    """
    service = StockDataService(db)

    try:
        result = await service.get_price_data_summary(symbol)

        if not result:
            raise HTTPException(status_code=404, detail=f"Stock {symbol} not found")

        return APIResponse(
            message="Data summary retrieved",
            data=DataSummaryResponse(
                symbol=result["symbol"],
                stock_id=result["stock_id"],
                has_data=result["has_data"],
                first_date=result.get("first_date"),
                last_date=result.get("last_date"),
                count=result.get("count", 0),
                listing_date=result.get("listing_date"),
            ),
        )
    finally:
        await service.close()


# =========================================================================
# Cache Management
# =========================================================================


@router.delete("/{symbol}/cache")
async def clear_stock_cache(
    symbol: str,
) -> APIResponse[dict[str, Any]]:
    """
    Clear cached data for a specific stock.

    Removes the real-time price cache for the specified symbol.
    """
    from api.core.redis import get_redis

    client = await get_redis()
    key = f"krxusd:stock:realtime:{symbol.upper()}"
    deleted = await client.delete(key)

    return APIResponse(
        message=f"Cache cleared for {symbol.upper()}" if deleted else f"No cache found for {symbol.upper()}",
        data={"symbol": symbol.upper(), "deleted": deleted > 0},
    )


@router.delete("/cache/all")
async def clear_all_stock_cache() -> APIResponse[dict[str, Any]]:
    """
    Clear all stock price caches.

    Use with caution - this will clear all real-time price caches.
    """
    deleted_count = await cache.delete_pattern("stock:realtime:*")

    return APIResponse(
        message=f"Cleared {deleted_count} cache entries",
        data={"deleted_count": deleted_count},
    )
