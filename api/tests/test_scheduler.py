"""
Tests for Realtime Data Update Scheduler

Tests cover:
1. Market hours utility functions
2. Active symbols tracking
3. Scheduler service
"""

import pytest
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock
import pytz

from api.core.market_hours import (
    KST,
    MARKET_OPEN_TIME,
    MARKET_CLOSE_TIME,
    MarketStatus,
    get_kst_now,
    to_kst,
    is_weekend,
    is_holiday,
    is_trading_day,
    get_next_trading_day,
    get_previous_trading_day,
    get_market_status,
    should_update_realtime,
    get_market_status_dict,
    get_trading_minutes_remaining,
)


class TestMarketHoursUtility:
    """Test market hours utility functions"""

    def test_get_kst_now(self):
        """Test get_kst_now returns KST timezone"""
        now = get_kst_now()
        assert now.tzinfo is not None
        assert now.tzinfo.zone == "Asia/Seoul"

    def test_to_kst_naive_datetime(self):
        """Test converting naive datetime to KST"""
        naive = datetime(2024, 1, 15, 10, 30)
        kst = to_kst(naive)
        assert kst.tzinfo is not None
        assert kst.tzinfo.zone == "Asia/Seoul"

    def test_to_kst_aware_datetime(self):
        """Test converting aware datetime to KST"""
        utc = pytz.UTC.localize(datetime(2024, 1, 15, 1, 30))  # 01:30 UTC = 10:30 KST
        kst = to_kst(utc)
        assert kst.hour == 10
        assert kst.minute == 30

    def test_is_weekend_saturday(self):
        """Test Saturday is detected as weekend"""
        saturday = date(2024, 1, 13)  # Saturday
        assert is_weekend(saturday) is True

    def test_is_weekend_sunday(self):
        """Test Sunday is detected as weekend"""
        sunday = date(2024, 1, 14)  # Sunday
        assert is_weekend(sunday) is True

    def test_is_weekend_weekday(self):
        """Test weekday is not weekend"""
        monday = date(2024, 1, 15)  # Monday
        assert is_weekend(monday) is False

    def test_is_holiday_new_year(self):
        """Test New Year is detected as holiday"""
        new_year = date(2024, 1, 1)
        assert is_holiday(new_year) is True

    def test_is_holiday_regular_day(self):
        """Test regular day is not holiday"""
        regular = date(2024, 1, 15)
        assert is_holiday(regular) is False

    def test_is_trading_day_weekday(self):
        """Test regular weekday is trading day"""
        monday = date(2024, 1, 15)  # Monday, not holiday
        assert is_trading_day(monday) is True

    def test_is_trading_day_weekend(self):
        """Test weekend is not trading day"""
        saturday = date(2024, 1, 13)
        assert is_trading_day(saturday) is False

    def test_is_trading_day_holiday(self):
        """Test holiday is not trading day"""
        new_year = date(2024, 1, 1)
        assert is_trading_day(new_year) is False

    def test_get_next_trading_day_from_friday(self):
        """Test next trading day from Friday is Monday"""
        friday = date(2024, 1, 12)  # Friday
        next_trading = get_next_trading_day(friday)
        assert next_trading == date(2024, 1, 15)  # Monday
        assert next_trading.weekday() == 0  # Monday

    def test_get_previous_trading_day_from_monday(self):
        """Test previous trading day from Monday is Friday"""
        monday = date(2024, 1, 15)  # Monday
        prev_trading = get_previous_trading_day(monday)
        assert prev_trading == date(2024, 1, 12)  # Friday
        assert prev_trading.weekday() == 4  # Friday

    def test_market_status_pre_market(self):
        """Test pre-market status (08:30 ~ 09:00)"""
        pre_market_time = KST.localize(datetime(2024, 1, 15, 8, 45))  # Monday 08:45 KST
        status = get_market_status(pre_market_time)

        assert status.status == MarketStatus.PRE_MARKET
        assert status.is_trading_time is False
        assert status.message == "장 시작 대기 중"

    def test_market_status_market_open(self):
        """Test market open status (09:00 ~ 15:30)"""
        market_time = KST.localize(datetime(2024, 1, 15, 10, 30))  # Monday 10:30 KST
        status = get_market_status(market_time)

        assert status.status == MarketStatus.MARKET_OPEN
        assert status.is_trading_time is True
        assert status.message == "장 운영 중"

    def test_market_status_after_hours(self):
        """Test after hours status (15:30 ~ 16:00)"""
        after_hours_time = KST.localize(datetime(2024, 1, 15, 15, 45))  # Monday 15:45 KST
        status = get_market_status(after_hours_time)

        assert status.status == MarketStatus.AFTER_HOURS
        assert status.is_trading_time is True  # Still update during after hours
        assert status.message == "시간외 거래 중"

    def test_market_status_closed(self):
        """Test market closed status (after 16:00)"""
        closed_time = KST.localize(datetime(2024, 1, 15, 17, 0))  # Monday 17:00 KST
        status = get_market_status(closed_time)

        assert status.status == MarketStatus.MARKET_CLOSED
        assert status.is_trading_time is False
        assert status.message == "장 종료"

    def test_market_status_weekend(self):
        """Test market closed on weekend"""
        weekend_time = KST.localize(datetime(2024, 1, 13, 10, 30))  # Saturday 10:30 KST
        status = get_market_status(weekend_time)

        assert status.status == MarketStatus.MARKET_CLOSED
        assert status.is_trading_time is False
        assert "휴장" in status.message

    def test_should_update_realtime_during_market_hours(self):
        """Test should_update_realtime returns True during market hours"""
        market_time = KST.localize(datetime(2024, 1, 15, 10, 30))

        with patch("api.core.market_hours.get_kst_now", return_value=market_time):
            assert should_update_realtime() is True

    def test_should_update_realtime_after_hours(self):
        """Test should_update_realtime returns False after hours"""
        closed_time = KST.localize(datetime(2024, 1, 15, 17, 0))

        with patch("api.core.market_hours.get_kst_now", return_value=closed_time):
            assert should_update_realtime() is False

    def test_get_market_status_dict(self):
        """Test get_market_status_dict returns proper dict format"""
        result = get_market_status_dict()

        assert isinstance(result, dict)
        assert "status" in result
        assert "is_trading_time" in result
        assert "current_time_kst" in result
        assert "message" in result

    def test_get_trading_minutes_remaining_during_market(self):
        """Test trading minutes remaining during market hours"""
        # 14:00 KST -> 90 minutes remaining until 15:30
        market_time = KST.localize(datetime(2024, 1, 15, 14, 0))

        with patch("api.core.market_hours.get_kst_now", return_value=market_time):
            remaining = get_trading_minutes_remaining()
            assert remaining == 90  # 15:30 - 14:00 = 90 minutes

    def test_get_trading_minutes_remaining_after_close(self):
        """Test trading minutes remaining after market close"""
        closed_time = KST.localize(datetime(2024, 1, 15, 17, 0))

        with patch("api.core.market_hours.get_kst_now", return_value=closed_time):
            remaining = get_trading_minutes_remaining()
            assert remaining == 0


class TestActiveSymbolsCache:
    """Test active symbols tracking with Redis"""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client"""
        mock_client = AsyncMock()
        return mock_client

    @pytest.mark.asyncio
    async def test_add_symbol(self, mock_redis):
        """Test adding a symbol to active list"""
        from api.core.redis import ActiveSymbolsCache

        cache = ActiveSymbolsCache()

        with patch("api.core.redis.get_redis", return_value=mock_redis):
            await cache.add("005930")

            # Verify zadd was called with symbol and current timestamp
            mock_redis.zadd.assert_called_once()
            call_args = mock_redis.zadd.call_args
            assert call_args[0][0] == "krxusd:active:symbols"
            assert "005930" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_remove_symbol(self, mock_redis):
        """Test removing a symbol from active list"""
        from api.core.redis import ActiveSymbolsCache

        cache = ActiveSymbolsCache()

        with patch("api.core.redis.get_redis", return_value=mock_redis):
            await cache.remove("005930")

            mock_redis.zrem.assert_called_once_with(
                "krxusd:active:symbols", "005930"
            )

    @pytest.mark.asyncio
    async def test_get_active_symbols(self, mock_redis):
        """Test getting active symbols list"""
        from api.core.redis import ActiveSymbolsCache

        cache = ActiveSymbolsCache()
        mock_redis.zrangebyscore.return_value = ["005930", "000660"]

        with patch("api.core.redis.get_redis", return_value=mock_redis):
            symbols = await cache.get_active_symbols()

            assert symbols == ["005930", "000660"]
            mock_redis.zrangebyscore.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_stale(self, mock_redis):
        """Test cleaning up stale symbols"""
        from api.core.redis import ActiveSymbolsCache

        cache = ActiveSymbolsCache()
        mock_redis.zremrangebyscore.return_value = 5

        with patch("api.core.redis.get_redis", return_value=mock_redis):
            removed = await cache.cleanup_stale()

            assert removed == 5
            mock_redis.zremrangebyscore.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_count(self, mock_redis):
        """Test getting active symbol count"""
        from api.core.redis import ActiveSymbolsCache

        cache = ActiveSymbolsCache()
        mock_redis.zcount.return_value = 10

        with patch("api.core.redis.get_redis", return_value=mock_redis):
            count = await cache.get_count()

            assert count == 10

    @pytest.mark.asyncio
    async def test_is_active_true(self, mock_redis):
        """Test checking if symbol is active (true case)"""
        from api.core.redis import ActiveSymbolsCache

        cache = ActiveSymbolsCache()
        # Score within TTL
        mock_redis.zscore.return_value = datetime.now().timestamp()

        with patch("api.core.redis.get_redis", return_value=mock_redis):
            is_active = await cache.is_active("005930")

            assert is_active is True

    @pytest.mark.asyncio
    async def test_is_active_false_not_found(self, mock_redis):
        """Test checking if symbol is active (not found)"""
        from api.core.redis import ActiveSymbolsCache

        cache = ActiveSymbolsCache()
        mock_redis.zscore.return_value = None

        with patch("api.core.redis.get_redis", return_value=mock_redis):
            is_active = await cache.is_active("005930")

            assert is_active is False


class TestSchedulerStateCache:
    """Test scheduler state cache"""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client"""
        mock_client = AsyncMock()
        return mock_client

    @pytest.mark.asyncio
    async def test_set_state(self, mock_redis):
        """Test setting scheduler state"""
        from api.core.redis import SchedulerStateCache

        cache = SchedulerStateCache()

        with patch("api.core.redis.get_redis", return_value=mock_redis):
            await cache.set_state(
                is_running=True,
                last_run_at=datetime.now(),
                stocks_updated=5,
                exchange_updated=True,
            )

            mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_state(self, mock_redis):
        """Test getting scheduler state"""
        from api.core.redis import SchedulerStateCache

        cache = SchedulerStateCache()
        mock_redis.get.return_value = '{"is_running": true, "stocks_updated": 5}'

        with patch("api.core.redis.get_redis", return_value=mock_redis):
            state = await cache.get_state()

            assert state is not None
            assert state["is_running"] is True
            assert state["stocks_updated"] == 5

    @pytest.mark.asyncio
    async def test_add_run_history(self, mock_redis):
        """Test adding run history"""
        from api.core.redis import SchedulerStateCache

        cache = SchedulerStateCache()

        with patch("api.core.redis.get_redis", return_value=mock_redis):
            await cache.add_run_history(
                run_time=datetime.now(),
                duration_ms=150,
                stocks_count=10,
                success=True,
            )

            mock_redis.lpush.assert_called_once()
            mock_redis.ltrim.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_run_history(self, mock_redis):
        """Test getting run history"""
        from api.core.redis import SchedulerStateCache

        cache = SchedulerStateCache()
        mock_redis.lrange.return_value = [
            '{"run_time": "2024-01-15T10:00:00", "success": true}',
            '{"run_time": "2024-01-15T09:59:00", "success": true}',
        ]

        with patch("api.core.redis.get_redis", return_value=mock_redis):
            history = await cache.get_run_history(limit=5)

            assert len(history) == 2
            assert history[0]["success"] is True


class TestRealtimeUpdateService:
    """Test realtime update service"""

    @pytest.mark.asyncio
    async def test_update_market_status(self):
        """Test market status update"""
        from api.services.scheduler_service import RealtimeUpdateService

        service = RealtimeUpdateService()
        market_time = KST.localize(datetime(2024, 1, 15, 10, 30))

        with patch("api.services.scheduler_service.get_market_status") as mock_status:
            mock_info = MagicMock()
            mock_info.status.value = "market_open"
            mock_info.is_trading_time = True
            mock_info.message = "장 운영 중"
            mock_status.return_value = mock_info

            with patch("api.services.scheduler_service.market_status_cache") as mock_cache:
                mock_cache.set = AsyncMock()

                result = await service.update_market_status()

                assert result["status"] == "market_open"
                assert result["is_trading_time"] is True

    @pytest.mark.asyncio
    async def test_update_active_stocks_market_closed(self):
        """Test that stock updates are skipped when market is closed"""
        from api.services.scheduler_service import RealtimeUpdateService

        service = RealtimeUpdateService()

        with patch("api.services.scheduler_service.should_update_realtime", return_value=False):
            with patch("api.services.scheduler_service.get_market_status") as mock_status:
                mock_info = MagicMock()
                mock_info.status.value = "market_closed"
                mock_status.return_value = mock_info

                result = await service.update_active_stocks()

                assert result["skipped"] is True
                assert result["stocks_updated"] == 0

    @pytest.mark.asyncio
    async def test_update_active_stocks_no_symbols(self):
        """Test stock updates with no active symbols"""
        from api.services.scheduler_service import RealtimeUpdateService

        service = RealtimeUpdateService()

        with patch("api.services.scheduler_service.should_update_realtime", return_value=True):
            with patch("api.services.scheduler_service.active_symbols_cache") as mock_cache:
                mock_cache.get_active_symbols = AsyncMock(return_value=[])

                result = await service.update_active_stocks()

                assert result["skipped"] is False
                assert result["stocks_updated"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_stale_symbols(self):
        """Test cleanup of stale symbols"""
        from api.services.scheduler_service import RealtimeUpdateService

        service = RealtimeUpdateService()

        with patch("api.services.scheduler_service.active_symbols_cache") as mock_cache:
            mock_cache.cleanup_stale = AsyncMock(return_value=3)

            removed = await service.cleanup_stale_symbols()

            assert removed == 3


class TestSchedulerFunctions:
    """Test scheduler module functions"""

    @pytest.mark.asyncio
    async def test_register_active_symbol(self):
        """Test registering active symbol"""
        from api.services.scheduler_service import register_active_symbol

        with patch("api.services.scheduler_service.active_symbols_cache") as mock_cache:
            mock_cache.add = AsyncMock()

            await register_active_symbol("005930")

            mock_cache.add.assert_called_once_with("005930")

    @pytest.mark.asyncio
    async def test_unregister_active_symbol(self):
        """Test unregistering active symbol"""
        from api.services.scheduler_service import unregister_active_symbol

        with patch("api.services.scheduler_service.active_symbols_cache") as mock_cache:
            mock_cache.remove = AsyncMock()

            await unregister_active_symbol("005930")

            mock_cache.remove.assert_called_once_with("005930")

    @pytest.mark.asyncio
    async def test_get_active_symbols(self):
        """Test getting active symbols"""
        from api.services.scheduler_service import get_active_symbols

        with patch("api.services.scheduler_service.active_symbols_cache") as mock_cache:
            mock_cache.get_active_symbols = AsyncMock(return_value=["005930", "000660"])

            symbols = await get_active_symbols()

            assert symbols == ["005930", "000660"]

    @pytest.mark.asyncio
    async def test_get_scheduler_status_disabled(self):
        """Test scheduler status when disabled"""
        from api.services.scheduler_service import get_scheduler_status

        with patch("api.services.scheduler_service.get_scheduler", return_value=None):
            with patch("api.services.scheduler_service.settings") as mock_settings:
                mock_settings.scheduler_enabled = False

                with patch("api.services.scheduler_service.scheduler_state_cache") as mock_state:
                    mock_state.get_state = AsyncMock(return_value=None)
                    mock_state.get_run_history = AsyncMock(return_value=[])

                    with patch("api.services.scheduler_service.active_symbols_cache") as mock_active:
                        mock_active.get_count = AsyncMock(return_value=0)

                        status = await get_scheduler_status()

                        assert status["running"] is False
