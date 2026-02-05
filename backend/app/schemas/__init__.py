"""Pydantic schemas for API."""
from .exchange import (
    ExchangeRateResponse,
    ExchangeHistoryItem,
    ExchangeHistoryResponse,
)
from .stock import (
    StockInfo,
    StockSearchResult,
    StockPriceHistory,
    StockUsdPriceHistory,
    UsdConvertedData,
)

__all__ = [
    "ExchangeRateResponse",
    "ExchangeHistoryItem", 
    "ExchangeHistoryResponse",
    "StockInfo",
    "StockSearchResult",
    "StockPriceHistory",
    "StockUsdPriceHistory",
    "UsdConvertedData",
]
