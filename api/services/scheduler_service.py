"""
Real-time Data Update Scheduler Service

Redis 기반 실시간 데이터 업데이트 스케줄러

Features:
- 1분 단위 주가/환율 데이터 Redis 업데이트
- 사용자가 조회 중인 종목에 대해서만 실시간 업데이트
- 메인 페이지 인기 종목 실시간 업데이트
- 장 운영 시간(09:00~15:30) 내에서만 동작

Implementation:
- APScheduler를 사용한 백그라운드 작업 스케줄링
- 조회 중인 종목 추적 로직 (Redis Sorted Set 활용)
- 외부 API 호출 최적화 (배치 요청)
"""

import asyncio
import logging
from datetime import datetime
from typing import Any
from decimal import Decimal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent

from api.core.config import settings
from api.core.database import async_session_factory
from api.core.market_hours import (
    should_update_realtime,
    get_market_status,
    MarketStatus,
    get_kst_now,
)
from api.core.redis import (
    active_symbols_cache,
    scheduler_state_cache,
    stock_realtime_cache,
    exchange_rate_cache,
    popular_stocks_cache,
    market_status_cache,
)
from api.services.stock_service import StockDataService
from api.services.exchange_service import ExchangeRateService

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


class RealtimeUpdateService:
    """
    실시간 데이터 업데이트 서비스

    스케줄러에서 호출되는 실제 업데이트 로직을 담당합니다.
    """

    async def update_active_stocks(self) -> dict[str, Any]:
        """
        현재 조회 중인 종목들의 실시간 가격을 업데이트합니다.

        Returns:
            업데이트 결과 정보
        """
        start_time = datetime.now()

        # 장 운영 시간이 아니면 스킵
        if not should_update_realtime():
            market_info = get_market_status()
            logger.debug(
                f"Skipping stock update - market not open. Status: {market_info.status.value}"
            )
            return {
                "skipped": True,
                "reason": f"Market not open ({market_info.status.value})",
                "stocks_updated": 0,
            }

        # 활성 심볼 조회 (최근 3분 이내 조회된 종목)
        active_symbols = await active_symbols_cache.get_active_symbols()

        if not active_symbols:
            logger.debug("No active symbols to update")
            return {
                "skipped": False,
                "stocks_updated": 0,
                "message": "No active symbols",
            }

        # 배치 크기 제한
        max_batch = settings.scheduler_max_batch_size
        symbols_to_update = active_symbols[:max_batch]

        if len(active_symbols) > max_batch:
            logger.warning(
                f"Active symbols ({len(active_symbols)}) exceeds max batch size ({max_batch}). "
                f"Updating first {max_batch} symbols only."
            )

        # 데이터베이스 세션 생성
        async with async_session_factory() as db:
            stock_service = StockDataService(db)

            try:
                # 배치로 실시간 가격 조회 (force_refresh=True)
                prices = await stock_service.get_realtime_prices_batch(
                    symbols=symbols_to_update,
                    force_refresh=True,
                )

                updated_count = sum(1 for p in prices.values() if p is not None)

                duration_ms = int(
                    (datetime.now() - start_time).total_seconds() * 1000
                )

                logger.info(
                    f"Updated {updated_count}/{len(symbols_to_update)} active stocks "
                    f"in {duration_ms}ms"
                )

                return {
                    "skipped": False,
                    "stocks_updated": updated_count,
                    "total_active": len(active_symbols),
                    "duration_ms": duration_ms,
                    "symbols": symbols_to_update,
                }
            except Exception as e:
                logger.error(f"Failed to update active stocks: {e}")
                raise

    async def update_exchange_rate(self) -> dict[str, Any]:
        """
        실시간 환율을 업데이트합니다.

        Returns:
            업데이트 결과 정보
        """
        start_time = datetime.now()

        # 환율은 장 운영 시간과 관계없이 항상 업데이트
        # (외환시장은 24시간 운영)
        async with async_session_factory() as db:
            exchange_service = ExchangeRateService(db)

            try:
                rate_data = await exchange_service.get_current_rate(force_refresh=True)

                duration_ms = int(
                    (datetime.now() - start_time).total_seconds() * 1000
                )

                logger.info(
                    f"Updated exchange rate: {rate_data['rate']} ({rate_data['source']}) "
                    f"in {duration_ms}ms"
                )

                return {
                    "rate": rate_data["rate"],
                    "source": rate_data["source"],
                    "duration_ms": duration_ms,
                }
            except Exception as e:
                logger.error(f"Failed to update exchange rate: {e}")
                raise
            finally:
                await exchange_service.close()

    async def update_market_status(self) -> dict[str, Any]:
        """
        시장 상태를 업데이트합니다.

        Returns:
            시장 상태 정보
        """
        market_info = get_market_status()

        # Redis 캐시에 시장 상태 저장
        await market_status_cache.set(
            status=market_info.status.value,
        )

        return {
            "status": market_info.status.value,
            "is_trading_time": market_info.is_trading_time,
            "message": market_info.message,
        }

    async def cleanup_stale_symbols(self) -> int:
        """
        오래된 활성 심볼을 정리합니다.

        Returns:
            제거된 심볼 수
        """
        removed = await active_symbols_cache.cleanup_stale()
        if removed > 0:
            logger.info(f"Cleaned up {removed} stale active symbols")
        return removed


# Singleton instance
_update_service: RealtimeUpdateService | None = None


def get_update_service() -> RealtimeUpdateService:
    """RealtimeUpdateService 싱글톤 인스턴스 반환"""
    global _update_service
    if _update_service is None:
        _update_service = RealtimeUpdateService()
    return _update_service


async def realtime_update_job() -> None:
    """
    실시간 업데이트 스케줄러 작업

    1분마다 실행되며:
    1. 시장 상태 업데이트
    2. 활성 종목 가격 업데이트
    3. 환율 업데이트
    4. 오래된 활성 심볼 정리
    """
    job_start = datetime.now()
    update_service = get_update_service()

    try:
        # 1. 시장 상태 업데이트
        market_result = await update_service.update_market_status()

        # 2. 활성 종목 가격 업데이트
        stock_result = await update_service.update_active_stocks()

        # 3. 환율 업데이트
        exchange_result = await update_service.update_exchange_rate()

        # 4. 오래된 심볼 정리
        removed_count = await update_service.cleanup_stale_symbols()

        # 실행 결과 기록
        duration_ms = int((datetime.now() - job_start).total_seconds() * 1000)

        await scheduler_state_cache.add_run_history(
            run_time=job_start,
            duration_ms=duration_ms,
            stocks_count=stock_result.get("stocks_updated", 0),
            success=True,
        )

        await scheduler_state_cache.set_state(
            is_running=True,
            last_run_at=job_start,
            stocks_updated=stock_result.get("stocks_updated", 0),
            exchange_updated=True,
        )

        logger.debug(
            f"Realtime update completed in {duration_ms}ms - "
            f"stocks: {stock_result.get('stocks_updated', 0)}, "
            f"exchange: {exchange_result.get('rate')}, "
            f"market: {market_result.get('status')}"
        )

    except Exception as e:
        duration_ms = int((datetime.now() - job_start).total_seconds() * 1000)

        await scheduler_state_cache.add_run_history(
            run_time=job_start,
            duration_ms=duration_ms,
            stocks_count=0,
            success=False,
            error=str(e)[:200],
        )

        logger.error(f"Realtime update job failed: {e}")


def job_listener(event: JobExecutionEvent) -> None:
    """스케줄러 작업 이벤트 리스너"""
    if event.exception:
        logger.error(
            f"Scheduler job {event.job_id} failed with exception: {event.exception}"
        )


async def init_scheduler() -> AsyncIOScheduler:
    """
    스케줄러 초기화 및 시작

    Returns:
        초기화된 AsyncIOScheduler 인스턴스
    """
    global _scheduler

    if not settings.scheduler_enabled:
        logger.info("Scheduler is disabled by configuration")
        return None

    if _scheduler is not None:
        logger.warning("Scheduler already initialized")
        return _scheduler

    # APScheduler 설정
    _scheduler = AsyncIOScheduler(
        timezone="Asia/Seoul",
        job_defaults={
            "coalesce": True,  # 밀린 작업 합치기
            "max_instances": 1,  # 동시 실행 제한
            "misfire_grace_time": 30,  # 30초 이내 지연은 허용
        },
    )

    # 이벤트 리스너 등록
    _scheduler.add_listener(job_listener, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

    # 실시간 업데이트 작업 등록 (1분 간격)
    _scheduler.add_job(
        realtime_update_job,
        trigger=IntervalTrigger(seconds=settings.scheduler_realtime_interval_seconds),
        id="realtime_update",
        name="Real-time Stock & Exchange Rate Update",
        replace_existing=True,
    )

    # 스케줄러 시작
    _scheduler.start()

    # 초기 상태 설정
    await scheduler_state_cache.set_state(
        is_running=True,
        last_run_at=None,
        stocks_updated=0,
        exchange_updated=False,
    )

    logger.info(
        f"Scheduler started with {settings.scheduler_realtime_interval_seconds}s interval"
    )

    return _scheduler


async def shutdown_scheduler() -> None:
    """스케줄러 종료"""
    global _scheduler

    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None

        await scheduler_state_cache.set_state(
            is_running=False,
            stocks_updated=0,
            exchange_updated=False,
        )

        logger.info("Scheduler shut down")


def get_scheduler() -> AsyncIOScheduler | None:
    """현재 스케줄러 인스턴스 반환"""
    return _scheduler


async def get_scheduler_status() -> dict[str, Any]:
    """
    스케줄러 상태 조회

    Returns:
        스케줄러 상태 정보
    """
    scheduler = get_scheduler()
    state = await scheduler_state_cache.get_state()
    history = await scheduler_state_cache.get_run_history(limit=5)

    active_count = await active_symbols_cache.get_count()
    market_info = get_market_status()

    if scheduler is None:
        return {
            "enabled": settings.scheduler_enabled,
            "running": False,
            "message": "Scheduler not initialized",
            "market_status": market_info.status.value,
            "is_trading_time": market_info.is_trading_time,
        }

    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run_time": job.next_run_time.isoformat() if job.next_run_time else None,
        })

    return {
        "enabled": settings.scheduler_enabled,
        "running": scheduler.running,
        "jobs": jobs,
        "state": state,
        "recent_history": history,
        "active_symbols_count": active_count,
        "market_status": market_info.status.value,
        "is_trading_time": market_info.is_trading_time,
        "config": {
            "realtime_interval_seconds": settings.scheduler_realtime_interval_seconds,
            "max_batch_size": settings.scheduler_max_batch_size,
            "active_symbol_ttl_seconds": settings.scheduler_active_symbol_ttl_seconds,
        },
    }


async def trigger_manual_update() -> dict[str, Any]:
    """
    수동으로 실시간 업데이트 트리거

    Returns:
        업데이트 결과
    """
    logger.info("Manual update triggered")
    await realtime_update_job()

    return {
        "triggered": True,
        "timestamp": datetime.now().isoformat(),
    }


async def register_active_symbol(symbol: str) -> None:
    """
    종목을 활성 목록에 등록

    사용자가 종목 상세 페이지를 조회할 때 호출됩니다.

    Args:
        symbol: 종목 코드
    """
    await active_symbols_cache.add(symbol.upper())
    logger.debug(f"Registered active symbol: {symbol}")


async def unregister_active_symbol(symbol: str) -> None:
    """
    종목을 활성 목록에서 제거

    Args:
        symbol: 종목 코드
    """
    await active_symbols_cache.remove(symbol.upper())
    logger.debug(f"Unregistered active symbol: {symbol}")


async def get_active_symbols() -> list[str]:
    """
    현재 활성화된 종목 목록 조회

    Returns:
        활성 종목 코드 목록
    """
    return await active_symbols_cache.get_active_symbols()
