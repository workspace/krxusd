"""
Real-time Data Update Scheduler Service

Redis 기반 실시간 데이터 업데이트 스케줄러

Features:
- 1분 단위 주가/환율 데이터 Redis 업데이트
- 사용자가 조회 중인 종목에 대해서만 실시간 업데이트
- 메인 페이지 인기 종목 실시간 업데이트
- 장 운영 시간(09:00~15:30) 내에서만 동작
- 장 마감 후(16:00) 인기 종목 데이터 선제적 업데이트 배치

Implementation:
- APScheduler를 사용한 백그라운드 작업 스케줄링
- 조회 중인 종목 추적 로직 (Redis Sorted Set 활용)
- 외부 API 호출 최적화 (배치 요청)
- 장 마감 후 인기 종목 일일 배치 업데이트
"""

import asyncio
import logging
from datetime import datetime, date, time
from typing import Any
from decimal import Decimal

import FinanceDataReader as fdr

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobExecutionEvent

from api.core.config import settings
from api.core.database import async_session_factory
from api.core.market_hours import (
    should_update_realtime,
    get_market_status,
    MarketStatus,
    get_kst_now,
    is_trading_day,
    KST,
)
from api.core.redis import (
    active_symbols_cache,
    scheduler_state_cache,
    stock_realtime_cache,
    exchange_rate_cache,
    popular_stocks_cache,
    market_status_cache,
    batch_update_state_cache,
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


class DailyBatchUpdateService:
    """
    일일 배치 업데이트 서비스

    장 마감 후(16:00) 인기 종목의 당일 종가 데이터를 선제적으로 업데이트합니다.

    대상:
    - 시가총액 상위 100종목
    - 거래량 상위 50종목

    이를 통해 다음날 사용자가 접속했을 때 Gap Filling 대기 시간을 제거합니다.
    """

    # 기본 설정
    DEFAULT_MARKET_CAP_TOP = 100  # 시가총액 상위 종목 수
    DEFAULT_VOLUME_TOP = 50       # 거래량 상위 종목 수
    MAX_RETRY_ATTEMPTS = 3        # 최대 재시도 횟수
    RETRY_DELAY_SECONDS = 60      # 재시도 간격 (초)
    BATCH_SIZE = 10               # 한 번에 처리할 종목 수

    async def get_popular_stocks(self) -> dict[str, list[str]]:
        """
        인기 종목 목록을 가져옵니다.

        Returns:
            dict with 'market_cap' and 'volume' keys,
            각각 종목 코드 리스트를 값으로 가짐
        """
        try:
            # KOSPI와 KOSDAQ 종목 리스트 가져오기
            kospi = fdr.StockListing("KOSPI")
            kosdaq = fdr.StockListing("KOSDAQ")

            # 데이터 병합
            all_stocks = []

            # KOSPI 종목 처리
            if not kospi.empty:
                kospi_data = kospi.copy()
                kospi_data["Market"] = "KOSPI"
                all_stocks.append(kospi_data)

            # KOSDAQ 종목 처리
            if not kosdaq.empty:
                kosdaq_data = kosdaq.copy()
                kosdaq_data["Market"] = "KOSDAQ"
                all_stocks.append(kosdaq_data)

            if not all_stocks:
                logger.warning("No stock data available from FDR")
                return {"market_cap": [], "volume": []}

            import pandas as pd
            df = pd.concat(all_stocks, ignore_index=True)

            # 컬럼명 정규화 (FDR 버전에 따라 다를 수 있음)
            code_col = "Code" if "Code" in df.columns else "Symbol"
            cap_col = "Marcap" if "Marcap" in df.columns else "MarketCap"
            volume_col = "Volume" if "Volume" in df.columns else "거래량"

            # 종목 코드 컬럼 확인
            if code_col not in df.columns:
                logger.error(f"Code column not found. Available: {df.columns.tolist()}")
                return {"market_cap": [], "volume": []}

            # 시가총액 상위 종목
            market_cap_stocks = []
            if cap_col in df.columns:
                df_cap = df.dropna(subset=[cap_col])
                df_cap = df_cap.sort_values(cap_col, ascending=False)
                market_cap_stocks = df_cap[code_col].head(self.DEFAULT_MARKET_CAP_TOP).tolist()
                logger.info(f"Found {len(market_cap_stocks)} market cap top stocks")
            else:
                logger.warning(f"Market cap column ({cap_col}) not found")

            # 거래량 상위 종목
            volume_stocks = []
            if volume_col in df.columns:
                df_vol = df.dropna(subset=[volume_col])
                df_vol = df_vol.sort_values(volume_col, ascending=False)
                volume_stocks = df_vol[code_col].head(self.DEFAULT_VOLUME_TOP).tolist()
                logger.info(f"Found {len(volume_stocks)} volume top stocks")
            else:
                logger.warning(f"Volume column ({volume_col}) not found")

            return {
                "market_cap": market_cap_stocks,
                "volume": volume_stocks,
            }

        except Exception as e:
            logger.error(f"Failed to get popular stocks: {e}")
            return {"market_cap": [], "volume": []}

    async def _update_single_stock(
        self,
        symbol: str,
        stock_service: StockDataService,
    ) -> dict[str, Any]:
        """
        단일 종목의 당일 데이터를 업데이트합니다.

        Args:
            symbol: 종목 코드
            stock_service: StockDataService 인스턴스

        Returns:
            업데이트 결과
        """
        try:
            # Gap Filling을 통해 데이터 동기화
            result = await stock_service.ensure_data_synced(
                symbol=symbol,
                auto_sync=True,
            )

            # 실시간 가격도 가져와서 Redis 캐시에 저장
            price_data = await stock_service.get_realtime_price(
                symbol=symbol,
                force_refresh=True,
            )

            return {
                "symbol": symbol,
                "success": True,
                "sync_case": result.get("sync_case"),
                "synced": result.get("synced", False),
                "price_updated": price_data is not None,
            }

        except Exception as e:
            logger.warning(f"Failed to update stock {symbol}: {e}")
            return {
                "symbol": symbol,
                "success": False,
                "error": str(e),
            }

    async def run_batch_update(
        self,
        market_cap_count: int | None = None,
        volume_count: int | None = None,
    ) -> dict[str, Any]:
        """
        인기 종목 배치 업데이트를 실행합니다.

        Args:
            market_cap_count: 시가총액 상위 종목 수 (기본값: 100)
            volume_count: 거래량 상위 종목 수 (기본값: 50)

        Returns:
            배치 업데이트 결과
        """
        start_time = datetime.now()
        today = date.today()

        # 거래일 체크
        if not is_trading_day(today):
            logger.info(f"Skipping batch update - not a trading day: {today}")
            return {
                "skipped": True,
                "reason": "Not a trading day",
                "date": today.isoformat(),
            }

        logger.info("Starting daily batch update for popular stocks")

        # 배치 업데이트 시작 상태 저장
        await batch_update_state_cache.set_state(
            status="running",
            started_at=start_time,
            target_date=today,
        )

        try:
            # 인기 종목 목록 가져오기
            popular = await self.get_popular_stocks()

            market_cap_stocks = popular["market_cap"][:market_cap_count or self.DEFAULT_MARKET_CAP_TOP]
            volume_stocks = popular["volume"][:volume_count or self.DEFAULT_VOLUME_TOP]

            # 중복 제거하여 전체 대상 목록 생성
            all_symbols = list(set(market_cap_stocks + volume_stocks))

            logger.info(
                f"Batch update targets: {len(market_cap_stocks)} market cap + "
                f"{len(volume_stocks)} volume = {len(all_symbols)} unique stocks"
            )

            # 결과 추적
            results = {
                "success": [],
                "failed": [],
            }

            # 데이터베이스 세션으로 배치 처리
            async with async_session_factory() as db:
                stock_service = StockDataService(db)

                # 배치 단위로 처리
                for i in range(0, len(all_symbols), self.BATCH_SIZE):
                    batch = all_symbols[i:i + self.BATCH_SIZE]
                    batch_num = i // self.BATCH_SIZE + 1
                    total_batches = (len(all_symbols) + self.BATCH_SIZE - 1) // self.BATCH_SIZE

                    logger.info(f"Processing batch {batch_num}/{total_batches}: {len(batch)} stocks")

                    # 병렬로 배치 내 종목 업데이트
                    tasks = [
                        self._update_single_stock(symbol, stock_service)
                        for symbol in batch
                    ]
                    batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                    for result in batch_results:
                        if isinstance(result, Exception):
                            results["failed"].append({
                                "error": str(result),
                            })
                        elif result.get("success"):
                            results["success"].append(result)
                        else:
                            results["failed"].append(result)

                    # 배치 간 짧은 대기 (API 제한 방지)
                    if i + self.BATCH_SIZE < len(all_symbols):
                        await asyncio.sleep(1)

                    # 진행 상황 업데이트
                    await batch_update_state_cache.set_state(
                        status="running",
                        started_at=start_time,
                        target_date=today,
                        progress={
                            "current": i + len(batch),
                            "total": len(all_symbols),
                            "percent": round((i + len(batch)) / len(all_symbols) * 100, 1),
                        }
                    )

            # Redis 인기 종목 캐시 갱신
            await self._update_popular_stocks_cache(market_cap_stocks, volume_stocks)

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            result_summary = {
                "success": True,
                "date": today.isoformat(),
                "duration_ms": duration_ms,
                "total_stocks": len(all_symbols),
                "market_cap_count": len(market_cap_stocks),
                "volume_count": len(volume_stocks),
                "updated_count": len(results["success"]),
                "failed_count": len(results["failed"]),
                "failed_symbols": [r.get("symbol", "unknown") for r in results["failed"][:10]],  # 처음 10개만
            }

            # 완료 상태 저장
            await batch_update_state_cache.set_state(
                status="completed",
                started_at=start_time,
                completed_at=datetime.now(),
                target_date=today,
                result=result_summary,
            )

            # 실행 기록 추가
            await batch_update_state_cache.add_history(
                run_date=today,
                duration_ms=duration_ms,
                stocks_count=len(all_symbols),
                success_count=len(results["success"]),
                failed_count=len(results["failed"]),
                success=True,
            )

            logger.info(
                f"Daily batch update completed: {len(results['success'])}/{len(all_symbols)} "
                f"stocks updated in {duration_ms}ms"
            )

            return result_summary

        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # 실패 상태 저장
            await batch_update_state_cache.set_state(
                status="failed",
                started_at=start_time,
                completed_at=datetime.now(),
                target_date=today,
                error=str(e)[:500],
            )

            # 실행 기록 추가
            await batch_update_state_cache.add_history(
                run_date=today,
                duration_ms=duration_ms,
                stocks_count=0,
                success_count=0,
                failed_count=0,
                success=False,
                error=str(e)[:200],
            )

            logger.error(f"Daily batch update failed: {e}")
            raise

    async def _update_popular_stocks_cache(
        self,
        market_cap_stocks: list[str],
        volume_stocks: list[str],
    ) -> None:
        """
        인기 종목 Redis 캐시를 갱신합니다.
        """
        try:
            # 각 종목의 현재 가격 정보 수집
            async with async_session_factory() as db:
                stock_service = StockDataService(db)

                # 시가총액 상위 종목 캐시
                market_cap_data = []
                for symbol in market_cap_stocks[:20]:  # 상위 20개만 캐시
                    try:
                        price = await stock_service.get_realtime_price(symbol)
                        if price:
                            market_cap_data.append({
                                "symbol": symbol,
                                **price,
                            })
                    except Exception:
                        pass

                if market_cap_data:
                    await popular_stocks_cache.set("market_cap", market_cap_data)

                # 거래량 상위 종목 캐시
                volume_data = []
                for symbol in volume_stocks[:20]:  # 상위 20개만 캐시
                    try:
                        price = await stock_service.get_realtime_price(symbol)
                        if price:
                            volume_data.append({
                                "symbol": symbol,
                                **price,
                            })
                    except Exception:
                        pass

                if volume_data:
                    await popular_stocks_cache.set("volume", volume_data)

            logger.info(
                f"Updated popular stocks cache: {len(market_cap_data)} market cap, "
                f"{len(volume_data)} volume stocks"
            )

        except Exception as e:
            logger.error(f"Failed to update popular stocks cache: {e}")

    async def run_with_retry(
        self,
        max_attempts: int | None = None,
        delay_seconds: int | None = None,
    ) -> dict[str, Any]:
        """
        재시도 로직을 포함한 배치 업데이트 실행

        Args:
            max_attempts: 최대 시도 횟수
            delay_seconds: 재시도 간격 (초)

        Returns:
            배치 업데이트 결과
        """
        max_attempts = max_attempts or self.MAX_RETRY_ATTEMPTS
        delay_seconds = delay_seconds or self.RETRY_DELAY_SECONDS

        last_error = None
        for attempt in range(1, max_attempts + 1):
            try:
                logger.info(f"Daily batch update attempt {attempt}/{max_attempts}")
                result = await self.run_batch_update()

                if result.get("skipped"):
                    return result

                return result

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Daily batch update attempt {attempt} failed: {e}"
                )

                if attempt < max_attempts:
                    logger.info(f"Retrying in {delay_seconds} seconds...")
                    await asyncio.sleep(delay_seconds)

        # 모든 시도 실패
        error_msg = f"Daily batch update failed after {max_attempts} attempts: {last_error}"
        logger.error(error_msg)

        return {
            "success": False,
            "error": error_msg,
            "attempts": max_attempts,
        }


# Singleton instances
_update_service: RealtimeUpdateService | None = None
_batch_update_service: DailyBatchUpdateService | None = None


def get_update_service() -> RealtimeUpdateService:
    """RealtimeUpdateService 싱글톤 인스턴스 반환"""
    global _update_service
    if _update_service is None:
        _update_service = RealtimeUpdateService()
    return _update_service


def get_batch_update_service() -> DailyBatchUpdateService:
    """DailyBatchUpdateService 싱글톤 인스턴스 반환"""
    global _batch_update_service
    if _batch_update_service is None:
        _batch_update_service = DailyBatchUpdateService()
    return _batch_update_service


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


async def daily_batch_update_job() -> None:
    """
    일일 배치 업데이트 스케줄러 작업

    장 마감 후 16:00에 실행되어 인기 종목 데이터를 선제적으로 업데이트합니다.
    """
    logger.info("Daily batch update job started")
    batch_service = get_batch_update_service()

    try:
        result = await batch_service.run_with_retry()

        if result.get("success"):
            logger.info(
                f"Daily batch update completed successfully: "
                f"{result.get('updated_count', 0)}/{result.get('total_stocks', 0)} stocks"
            )
        elif result.get("skipped"):
            logger.info(f"Daily batch update skipped: {result.get('reason')}")
        else:
            logger.error(f"Daily batch update failed: {result.get('error')}")

    except Exception as e:
        logger.error(f"Daily batch update job error: {e}")


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

    # 일일 배치 업데이트 작업 등록 (매일 16:00 KST)
    _scheduler.add_job(
        daily_batch_update_job,
        trigger=CronTrigger(
            hour=settings.scheduler_daily_batch_hour,
            minute=settings.scheduler_daily_batch_minute,
            timezone="Asia/Seoul",
        ),
        id="daily_batch_update",
        name="Daily Batch Update for Popular Stocks",
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


# =========================================================================
# Daily Batch Update Functions
# =========================================================================

async def trigger_daily_batch_update() -> dict[str, Any]:
    """
    일일 배치 업데이트를 수동으로 트리거

    Returns:
        배치 업데이트 결과
    """
    logger.info("Manual daily batch update triggered")
    batch_service = get_batch_update_service()
    return await batch_service.run_with_retry()


async def get_batch_update_status() -> dict[str, Any]:
    """
    일일 배치 업데이트 상태 조회

    Returns:
        배치 업데이트 상태 정보
    """
    state = await batch_update_state_cache.get_state()
    history = await batch_update_state_cache.get_history(limit=5)

    scheduler = get_scheduler()
    next_run = None

    if scheduler:
        job = scheduler.get_job("daily_batch_update")
        if job and job.next_run_time:
            next_run = job.next_run_time.isoformat()

    return {
        "state": state,
        "recent_history": history,
        "next_run_at": next_run,
        "config": {
            "scheduled_time": f"{settings.scheduler_daily_batch_hour:02d}:{settings.scheduler_daily_batch_minute:02d}",
            "market_cap_top": DailyBatchUpdateService.DEFAULT_MARKET_CAP_TOP,
            "volume_top": DailyBatchUpdateService.DEFAULT_VOLUME_TOP,
            "max_retry_attempts": DailyBatchUpdateService.MAX_RETRY_ATTEMPTS,
        },
    }


async def get_popular_stocks_for_batch() -> dict[str, list[str]]:
    """
    배치 업데이트 대상 인기 종목 목록 조회 (미리보기용)

    Returns:
        시가총액/거래량 상위 종목 목록
    """
    batch_service = get_batch_update_service()
    return await batch_service.get_popular_stocks()
