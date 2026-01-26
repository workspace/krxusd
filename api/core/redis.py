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


# Singleton instances
cache = RedisCache()
stock_realtime_cache = StockRealtimeCache()
stock_minute_cache = StockMinuteCache()
exchange_rate_cache = ExchangeRateCache()
popular_stocks_cache = PopularStocksCache()
market_status_cache = MarketStatusCache()
