from fastapi import APIRouter

from .stocks import router as stocks_router
from .exchange import router as exchange_router
from .health import router as health_router
from .scheduler import router as scheduler_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["Health"])
api_router.include_router(stocks_router, prefix="/stocks", tags=["Stocks"])
api_router.include_router(exchange_router, prefix="/exchange", tags=["Exchange Rate"])
api_router.include_router(scheduler_router)

__all__ = ["api_router"]
