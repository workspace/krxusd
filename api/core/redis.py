"""
Redis Cache Module for KRXUSD

Key Structure Design:
- krxusd:stock:realtime:{symbol}     - 당일 실시간 주가 (1분 단위)
- krxusd:stock:minute:{symbol}:{date} - 당일 분 단위 OHLCV 데이터
- krxusd:exchange:realtime            - 실시간 환율
- krxusd:exchange:minute:{date}       - 당일 분 단위 환율 데이터
- krxusd:popular:{ranking_type}       - 인기 종목 리스트 (volume, value, gain, loss)
- krxusd:market:status                - 시장 상태 (장전/장중/장후)
- krxusd:cache:{key}                  - 일반 캐시 데이터
"""

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from collections.abc import Callable

from redis.asyncio import Redis, from_url

from .config import settings

redis_client: Redis | None = None


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal types"""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        return super().default(obj)


def json_dumps(obj: Any) -> str:
    """JSON dumps with Decimal support"""
    return json.dumps(obj, cls=DecimalEncoder, ensure_ascii=False)


def json_loads(s: str) -> Any:
    """JSON loads wrapper"""
    return json.loads(s)


async def init_redis() -> Redis:
    """Initialize Redis connection"""
    global redis_client
    redis_client = await from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    return redis_client


async def close_redis() -> None:
    """Close Redis connection"""
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


async def get_redis() -> Redis:
    """Dependency for getting Redis client"""
    if redis_client is None:
        await init_redis()
    return redis_client  # type: ignore


class RedisCache:
    """Helper class for Redis caching operations"""

    def __init__(self, prefix: str = "krxusd"):
        self.prefix = prefix

    def _make_key(self, key: str) -> str:
        return f"{self.prefix}:{key}"

    async def get(self, key: str) -> Any | None:
        """Get value from cache"""
        client = await get_redis()
        value = await client.get(self._make_key(key))
        if value:
            return json_loads(value)
        return None

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        """Set value in cache with TTL (default 60 seconds)"""
        client = await get_redis()
        await client.set(self._make_key(key), json_dumps(value), ex=ttl)

    async def delete(self, key: str) -> None:
        """Delete value from cache"""
        client = await get_redis()
        await client.delete(self._make_key(key))

    async def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        client = await get_redis()
        return await client.exists(self._make_key(key)) > 0

    async def get_or_set(
        self, key: str, getter: Callable, ttl: int = 60
    ) -> Any:
        """Get from cache or set if not exists"""
        value = await self.get(key)
        if value is None:
            value = await getter()
            await self.set(key, value, ttl)
        return value

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        client = await get_redis()
        full_pattern = self._make_key(pattern)
        keys = []
        async for key in client.scan_iter(match=full_pattern):
            keys.append(key)
        if keys:
            return await client.delete(*keys)
        return 0


class StockRealtimeCache:
    """
    실시간 주가 데이터 캐시

    Key: krxusd:stock:realtime:{symbol}
    TTL: 120초 (2분 - 장중 1분 갱신 기준 여유분)
    """

    def __init__(self):
        self.prefix = "krxusd:stock:realtime"
        self.ttl = 120  # 2 minutes

    def _make_key(self, symbol: str) -> str:
        return f"{self.prefix}:{symbol.upper()}"

    async def get(self, symbol: str) -> dict | None:
        """Get realtime stock price"""
        client = await get_redis()
        value = await client.get(self._make_key(symbol))
        return json_loads(value) if value else None

    async def set(self, symbol: str, data: dict) -> None:
        """Set realtime stock price"""
        client = await get_redis()
        data["updated_at"] = datetime.now().isoformat()
        await client.set(self._make_key(symbol), json_dumps(data), ex=self.ttl)

    async def mget(self, symbols: list[str]) -> dict[str, dict | None]:
        """Get multiple stock prices"""
        client = await get_redis()
        keys = [self._make_key(s) for s in symbols]
        values = await client.mget(keys)
        return {
            symbol: json_loads(v) if v else None
            for symbol, v in zip(symbols, values)
        }

    async def mset(self, data: dict[str, dict]) -> None:
        """Set multiple stock prices"""
        client = await get_redis()
        now = datetime.now().isoformat()
        pipe = client.pipeline()
        for symbol, value in data.items():
            value["updated_at"] = now
            pipe.set(self._make_key(symbol), json_dumps(value), ex=self.ttl)
        await pipe.execute()


class StockMinuteCache:
    """
    당일 분 단위 OHLCV 데이터 캐시

    Key: krxusd:stock:minute:{symbol}:{date}
    TTL: 장 종료 후 자정까지 (최대 24시간)
    Structure: Sorted Set (score = timestamp)
    """

    def __init__(self):
        self.prefix = "krxusd:stock:minute"
        self.ttl = 86400  # 24 hours

    def _make_key(self, symbol: str, trade_date: date | None = None) -> str:
        if trade_date is None:
            trade_date = date.today()
        return f"{self.prefix}:{symbol.upper()}:{trade_date.isoformat()}"

    async def add(self, symbol: str, timestamp: datetime, data: dict) -> None:
        """Add minute data point"""
        client = await get_redis()
        key = self._make_key(symbol)
        score = timestamp.timestamp()
        data["timestamp"] = timestamp.isoformat()
        await client.zadd(key, {json_dumps(data): score})
        await client.expire(key, self.ttl)

    async def get_range(
        self,
        symbol: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        trade_date: date | None = None,
    ) -> list[dict]:
        """Get minute data in time range"""
        client = await get_redis()
        key = self._make_key(symbol, trade_date)
        start_score = start_time.timestamp() if start_time else "-inf"
        end_score = end_time.timestamp() if end_time else "+inf"
        values = await client.zrangebyscore(key, start_score, end_score)
        return [json_loads(v) for v in values]

    async def get_latest(self, symbol: str, count: int = 1) -> list[dict]:
        """Get latest N minute data points"""
        client = await get_redis()
        key = self._make_key(symbol)
        values = await client.zrevrange(key, 0, count - 1)
        return [json_loads(v) for v in values]


class ExchangeRateCache:
    """
    실시간 환율 데이터 캐시

    Key: krxusd:exchange:realtime
    TTL: 60초 (1분) - 1분 단위 업데이트
    """

    def __init__(self):
        self.realtime_key = "krxusd:exchange:realtime"
        self.minute_prefix = "krxusd:exchange:minute"
        self.ttl = 60  # 1 minute - matches update frequency

    async def get_realtime(self) -> dict | None:
        """Get current exchange rate"""
        client = await get_redis()
        value = await client.get(self.realtime_key)
        return json_loads(value) if value else None

    async def set_realtime(self, rate: Decimal, source: str = "unknown") -> None:
        """Set current exchange rate"""
        client = await get_redis()
        data = {
            "rate": str(rate),
            "currency_pair": "USD/KRW",
            "source": source,
            "updated_at": datetime.now().isoformat(),
        }
        await client.set(self.realtime_key, json_dumps(data), ex=self.ttl)

    async def add_minute_data(self, rate: Decimal, timestamp: datetime) -> None:
        """Add minute exchange rate data"""
        client = await get_redis()
        key = f"{self.minute_prefix}:{timestamp.date().isoformat()}"
        data = {
            "rate": str(rate),
            "timestamp": timestamp.isoformat(),
        }
        await client.zadd(key, {json_dumps(data): timestamp.timestamp()})
        await client.expire(key, 86400)  # 24 hours


class PopularStocksCache:
    """
    인기 종목 캐시

    Key: krxusd:popular:{ranking_type}
    Types: volume (거래량), value (거래대금), gain (상승률), loss (하락률)
    TTL: 300초 (5분)
    """

    RANKING_TYPES = ("volume", "value", "gain", "loss")

    def __init__(self):
        self.prefix = "krxusd:popular"
        self.ttl = 300  # 5 minutes

    def _make_key(self, ranking_type: str) -> str:
        if ranking_type not in self.RANKING_TYPES:
            raise ValueError(f"Invalid ranking type: {ranking_type}")
        return f"{self.prefix}:{ranking_type}"

    async def get(self, ranking_type: str) -> list[dict] | None:
        """Get popular stocks by ranking type"""
        client = await get_redis()
        value = await client.get(self._make_key(ranking_type))
        return json_loads(value) if value else None

    async def set(self, ranking_type: str, stocks: list[dict]) -> None:
        """Set popular stocks list"""
        client = await get_redis()
        data = {
            "stocks": stocks,
            "updated_at": datetime.now().isoformat(),
        }
        await client.set(self._make_key(ranking_type), json_dumps(data), ex=self.ttl)

    async def get_all(self) -> dict[str, list[dict] | None]:
        """Get all ranking types"""
        client = await get_redis()
        keys = [self._make_key(t) for t in self.RANKING_TYPES]
        values = await client.mget(keys)
        return {
            ranking_type: json_loads(v)["stocks"] if v else None
            for ranking_type, v in zip(self.RANKING_TYPES, values)
        }


class MarketStatusCache:
    """
    시장 상태 캐시

    Key: krxusd:market:status
    TTL: 60초 (1분)
    Status: pre_market, market_open, market_close, after_hours
    """

    def __init__(self):
        self.key = "krxusd:market:status"
        self.ttl = 60

    async def get(self) -> dict | None:
        """Get market status"""
        client = await get_redis()
        value = await client.get(self.key)
        return json_loads(value) if value else None

    async def set(
        self,
        status: str,
        kospi_index: Decimal | None = None,
        kosdaq_index: Decimal | None = None,
    ) -> None:
        """Set market status"""
        client = await get_redis()
        data = {
            "status": status,
            "kospi_index": str(kospi_index) if kospi_index else None,
            "kosdaq_index": str(kosdaq_index) if kosdaq_index else None,
            "updated_at": datetime.now().isoformat(),
        }
        await client.set(self.key, json_dumps(data), ex=self.ttl)


class ActiveSymbolsCache:
    """
    사용자가 현재 조회 중인 종목 추적 캐시

    Key: krxusd:active:symbols
    Structure: Set (각 심볼에 TTL로 자동 만료)

    Redis Set을 사용하여 현재 조회 중인 종목을 추적합니다.
    각 종목은 마지막 조회 시간을 score로 하는 Sorted Set으로 관리되어
    오래된 항목은 자동으로 비활성화 처리됩니다.
    """

    def __init__(self):
        self.key = "krxusd:active:symbols"
        self.ttl = 180  # 3분 (사용자가 페이지를 떠난 후 3분 동안 유지)

    async def add(self, symbol: str) -> None:
        """
        심볼을 활성 목록에 추가 (현재 시간을 score로 사용)

        사용자가 종목 상세 페이지를 조회할 때 호출됩니다.
        """
        client = await get_redis()
        now = datetime.now().timestamp()
        await client.zadd(self.key, {symbol.upper(): now})

    async def remove(self, symbol: str) -> None:
        """심볼을 활성 목록에서 제거"""
        client = await get_redis()
        await client.zrem(self.key, symbol.upper())

    async def get_active_symbols(self, max_age_seconds: int | None = None) -> list[str]:
        """
        현재 활성화된 심볼 목록 조회

        Args:
            max_age_seconds: 이 시간(초) 내에 조회된 심볼만 반환.
                            None이면 TTL(3분) 이내 모든 심볼 반환.

        Returns:
            활성 심볼 목록
        """
        client = await get_redis()

        if max_age_seconds is None:
            max_age_seconds = self.ttl

        # 현재 시간 기준으로 max_age_seconds 이내의 심볼만 조회
        min_score = datetime.now().timestamp() - max_age_seconds

        # ZRANGEBYSCORE로 최근 활성 심볼만 가져옴
        symbols = await client.zrangebyscore(self.key, min_score, "+inf")
        return [s for s in symbols]

    async def cleanup_stale(self) -> int:
        """
        TTL이 지난 오래된 심볼 제거

        Returns:
            제거된 심볼 수
        """
        client = await get_redis()
        cutoff = datetime.now().timestamp() - self.ttl
        # score가 cutoff보다 작은 항목 제거
        removed = await client.zremrangebyscore(self.key, "-inf", cutoff)
        return removed

    async def get_count(self) -> int:
        """현재 활성 심볼 수 조회"""
        client = await get_redis()
        min_score = datetime.now().timestamp() - self.ttl
        return await client.zcount(self.key, min_score, "+inf")

    async def refresh(self, symbol: str) -> None:
        """
        심볼의 마지막 조회 시간을 갱신

        사용자가 계속 페이지에 머무르고 있을 때 호출됩니다.
        """
        await self.add(symbol)

    async def is_active(self, symbol: str) -> bool:
        """심볼이 현재 활성 상태인지 확인"""
        client = await get_redis()
        min_score = datetime.now().timestamp() - self.ttl
        score = await client.zscore(self.key, symbol.upper())
        if score is None:
            return False
        return score >= min_score


class SchedulerStateCache:
    """
    스케줄러 상태 관리 캐시

    Key: krxusd:scheduler:state
    스케줄러의 실행 상태, 마지막 실행 시간 등을 저장합니다.
    """

    def __init__(self):
        self.key = "krxusd:scheduler:state"
        self.history_key = "krxusd:scheduler:history"
        self.ttl = 86400  # 24시간

    async def set_state(
        self,
        is_running: bool,
        last_run_at: datetime | None = None,
        next_run_at: datetime | None = None,
        stocks_updated: int = 0,
        exchange_updated: bool = False,
    ) -> None:
        """스케줄러 상태 저장"""
        client = await get_redis()
        data = {
            "is_running": is_running,
            "last_run_at": last_run_at.isoformat() if last_run_at else None,
            "next_run_at": next_run_at.isoformat() if next_run_at else None,
            "stocks_updated": stocks_updated,
            "exchange_updated": exchange_updated,
            "updated_at": datetime.now().isoformat(),
        }
        await client.set(self.key, json_dumps(data), ex=self.ttl)

    async def get_state(self) -> dict | None:
        """스케줄러 상태 조회"""
        client = await get_redis()
        value = await client.get(self.key)
        return json_loads(value) if value else None

    async def add_run_history(
        self,
        run_time: datetime,
        duration_ms: int,
        stocks_count: int,
        success: bool,
        error: str | None = None,
    ) -> None:
        """스케줄러 실행 기록 추가 (최근 100개 유지)"""
        client = await get_redis()
        data = {
            "run_time": run_time.isoformat(),
            "duration_ms": duration_ms,
            "stocks_count": stocks_count,
            "success": success,
            "error": error,
        }
        # 최신 기록을 앞에 추가
        await client.lpush(self.history_key, json_dumps(data))
        # 최근 100개만 유지
        await client.ltrim(self.history_key, 0, 99)
        await client.expire(self.history_key, self.ttl)

    async def get_run_history(self, limit: int = 10) -> list[dict]:
        """최근 실행 기록 조회"""
        client = await get_redis()
        history = await client.lrange(self.history_key, 0, limit - 1)
        return [json_loads(h) for h in history]


class BatchUpdateStateCache:
    """
    일일 배치 업데이트 상태 관리 캐시

    Key: krxusd:batch:state - 현재 배치 업데이트 상태
    Key: krxusd:batch:history - 배치 업데이트 실행 기록
    TTL: 7일 (히스토리 보관)
    """

    def __init__(self):
        self.state_key = "krxusd:batch:state"
        self.history_key = "krxusd:batch:history"
        self.ttl = 604800  # 7일

    async def set_state(
        self,
        status: str,  # "idle", "running", "completed", "failed"
        started_at: datetime | None = None,
        completed_at: datetime | None = None,
        target_date: date | None = None,
        progress: dict | None = None,
        result: dict | None = None,
        error: str | None = None,
    ) -> None:
        """배치 업데이트 상태 저장"""
        client = await get_redis()
        data = {
            "status": status,
            "started_at": started_at.isoformat() if started_at else None,
            "completed_at": completed_at.isoformat() if completed_at else None,
            "target_date": target_date.isoformat() if target_date else None,
            "progress": progress,
            "result": result,
            "error": error,
            "updated_at": datetime.now().isoformat(),
        }
        await client.set(self.state_key, json_dumps(data), ex=self.ttl)

    async def get_state(self) -> dict | None:
        """배치 업데이트 상태 조회"""
        client = await get_redis()
        value = await client.get(self.state_key)
        return json_loads(value) if value else None

    async def add_history(
        self,
        run_date: date,
        duration_ms: int,
        stocks_count: int,
        success_count: int,
        failed_count: int,
        success: bool,
        error: str | None = None,
    ) -> None:
        """배치 업데이트 실행 기록 추가 (최근 30개 유지)"""
        client = await get_redis()
        data = {
            "run_date": run_date.isoformat(),
            "run_time": datetime.now().isoformat(),
            "duration_ms": duration_ms,
            "stocks_count": stocks_count,
            "success_count": success_count,
            "failed_count": failed_count,
            "success": success,
            "error": error,
        }
        # 최신 기록을 앞에 추가
        await client.lpush(self.history_key, json_dumps(data))
        # 최근 30개만 유지 (약 1개월)
        await client.ltrim(self.history_key, 0, 29)
        await client.expire(self.history_key, self.ttl)

    async def get_history(self, limit: int = 10) -> list[dict]:
        """최근 실행 기록 조회"""
        client = await get_redis()
        history = await client.lrange(self.history_key, 0, limit - 1)
        return [json_loads(h) for h in history]

    async def get_last_success_date(self) -> date | None:
        """마지막 성공한 배치 업데이트 날짜 조회"""
        history = await self.get_history(limit=30)
        for record in history:
            if record.get("success"):
                return date.fromisoformat(record["run_date"])
        return None


# Singleton instances
cache = RedisCache()
stock_realtime_cache = StockRealtimeCache()
stock_minute_cache = StockMinuteCache()
exchange_rate_cache = ExchangeRateCache()
popular_stocks_cache = PopularStocksCache()
market_status_cache = MarketStatusCache()
active_symbols_cache = ActiveSymbolsCache()
scheduler_state_cache = SchedulerStateCache()
batch_update_state_cache = BatchUpdateStateCache()
