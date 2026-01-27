"""
Unit Tests for Stock Data Service

Tests the stock data collection service including:
- Real-time price fetching
- Gap Filling strategy (Case A/B/C)
- Batch operations
- Redis caching integration
"""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import pandas as pd

from api.services.stock_service import (
    StockDataService,
    StockDataServiceError,
    StockNotFoundError,
    StockDataFetchError,
    SyncCase,
    DEFAULT_HISTORY_DAYS,
    MAX_HISTORY_YEARS,
)


class TestSyncCase:
    """Test SyncCase enum values"""

    def test_sync_case_values(self):
        assert SyncCase.CASE_A_NO_DATA.value == "no_data"
        assert SyncCase.CASE_B_GAP_DETECTED.value == "gap_detected"
        assert SyncCase.CASE_C_UP_TO_DATE.value == "up_to_date"


class TestStockDataService:
    """Test StockDataService methods"""

    @pytest.fixture
    def mock_db(self):
        """Create a mock database session"""
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        """Create service instance with mock db"""
        return StockDataService(mock_db)

    def test_get_yesterday(self, service):
        """Test _get_yesterday returns yesterday's date"""
        yesterday = service._get_yesterday()
        assert yesterday == date.today() - timedelta(days=1)

    def test_calculate_sync_start_date_with_listing_date(self, service):
        """Test start date calculation uses listing date when available"""
        # Recent listing date
        listing_date = date.today() - timedelta(days=100)
        result = service._calculate_sync_start_date(listing_date)
        assert result == listing_date

    def test_calculate_sync_start_date_caps_at_max_years(self, service):
        """Test start date is capped at MAX_HISTORY_YEARS"""
        # Very old listing date (20 years ago)
        old_listing = date.today() - timedelta(days=20 * 365)
        result = service._calculate_sync_start_date(old_listing)

        # Should be capped at MAX_HISTORY_YEARS
        max_start = date.today() - timedelta(days=MAX_HISTORY_YEARS * 365)
        assert result == max_start

    def test_calculate_sync_start_date_without_listing_date(self, service):
        """Test start date uses default when no listing date"""
        result = service._calculate_sync_start_date(None)
        expected = date.today() - timedelta(days=DEFAULT_HISTORY_DAYS)
        assert result == expected


class TestRealtimePriceFetching:
    """Test real-time price fetching from external sources"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return StockDataService(mock_db)

    @pytest.mark.asyncio
    @patch("api.services.stock_service.fdr")
    async def test_fetch_from_fdr_success(self, mock_fdr, service):
        """Test successful fetch from FinanceDataReader"""
        # Create mock DataFrame
        mock_data = pd.DataFrame({
            "Open": [70000.0, 71000.0],
            "High": [72000.0, 73000.0],
            "Low": [69000.0, 70000.0],
            "Close": [71000.0, 72000.0],
            "Volume": [1000000, 1100000],
        }, index=pd.to_datetime(["2025-01-20", "2025-01-21"]))

        mock_fdr.DataReader.return_value = mock_data

        result = await service._fetch_from_fdr("005930")

        assert result["symbol"] == "005930"
        assert result["close_price"] == "72000.0"
        assert result["volume"] == 1100000
        assert result["source"] == "financedatareader"
        assert "change" in result
        assert "change_percent" in result

    @pytest.mark.asyncio
    @patch("api.services.stock_service.fdr")
    async def test_fetch_from_fdr_empty_data(self, mock_fdr, service):
        """Test FDR fetch with empty data raises error"""
        mock_fdr.DataReader.return_value = pd.DataFrame()

        with pytest.raises(ValueError, match="No data returned"):
            await service._fetch_from_fdr("INVALID")


class TestGapFillingStrategy:
    """
    Test Gap Filling Strategy implementation.

    Gap Filling Strategy:
    - Case A (No Data): No price data exists → Full collection from listing_date to yesterday
    - Case B (Gap Detected): last_saved_date < yesterday → Collect missing dates only
    - Case C (Up-to-date): last_saved_date >= yesterday → No action needed
    """

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return StockDataService(mock_db)

    @pytest.mark.asyncio
    async def test_analyze_case_a_no_data_with_listing_date(self, service, mock_db):
        """Test Case A: No data + listing date → sync from listing_date to yesterday"""
        # Mock stock with listing date
        mock_stock = MagicMock()
        mock_stock.id = 1
        mock_stock.symbol = "005930"
        mock_stock.listing_date = date(2020, 1, 15)

        # First execute returns stock, second returns None (no price data)
        mock_stock_result = AsyncMock()
        mock_stock_result.scalar_one_or_none.return_value = mock_stock

        mock_price_result = AsyncMock()
        mock_price_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_stock_result, mock_price_result]

        sync_case, start_date, end_date = await service.analyze_sync_status(stock_id=1)

        assert sync_case == SyncCase.CASE_A_NO_DATA
        # Should start from listing date (capped at MAX_HISTORY_YEARS)
        max_start = date.today() - timedelta(days=MAX_HISTORY_YEARS * 365)
        expected_start = max(mock_stock.listing_date, max_start)
        assert start_date == expected_start
        # End date should be yesterday
        assert end_date == service._get_yesterday()

    @pytest.mark.asyncio
    async def test_analyze_case_a_no_data_without_listing_date(self, service, mock_db):
        """Test Case A: No data + no listing date → sync from default_days to yesterday"""
        mock_stock = MagicMock()
        mock_stock.id = 1
        mock_stock.symbol = "005930"
        mock_stock.listing_date = None  # No listing date

        mock_stock_result = AsyncMock()
        mock_stock_result.scalar_one_or_none.return_value = mock_stock

        mock_price_result = AsyncMock()
        mock_price_result.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_stock_result, mock_price_result]

        sync_case, start_date, end_date = await service.analyze_sync_status(stock_id=1)

        assert sync_case == SyncCase.CASE_A_NO_DATA
        # Should use default history days
        expected_start = date.today() - timedelta(days=DEFAULT_HISTORY_DAYS)
        assert start_date == expected_start
        assert end_date == service._get_yesterday()

    @pytest.mark.asyncio
    async def test_analyze_case_b_gap_detected(self, service, mock_db):
        """Test Case B: last_saved_date < yesterday → sync gap only"""
        mock_stock = MagicMock()
        mock_stock.id = 1
        mock_stock.symbol = "005930"

        # Last saved date is 10 days ago
        last_saved_date = date.today() - timedelta(days=10)

        mock_stock_result = AsyncMock()
        mock_stock_result.scalar_one_or_none.return_value = mock_stock

        mock_price_result = AsyncMock()
        mock_price_result.scalar_one_or_none.return_value = last_saved_date

        mock_db.execute.side_effect = [mock_stock_result, mock_price_result]

        sync_case, start_date, end_date = await service.analyze_sync_status(stock_id=1)

        assert sync_case == SyncCase.CASE_B_GAP_DETECTED
        # Start should be day after last_saved_date
        assert start_date == last_saved_date + timedelta(days=1)
        # End should be yesterday
        assert end_date == service._get_yesterday()

    @pytest.mark.asyncio
    async def test_analyze_case_c_up_to_date_yesterday(self, service, mock_db):
        """Test Case C: last_saved_date == yesterday → no sync needed"""
        mock_stock = MagicMock()
        mock_stock.id = 1
        mock_stock.symbol = "005930"

        # Last saved date is yesterday
        yesterday = date.today() - timedelta(days=1)

        mock_stock_result = AsyncMock()
        mock_stock_result.scalar_one_or_none.return_value = mock_stock

        mock_price_result = AsyncMock()
        mock_price_result.scalar_one_or_none.return_value = yesterday

        mock_db.execute.side_effect = [mock_stock_result, mock_price_result]

        sync_case, start_date, end_date = await service.analyze_sync_status(stock_id=1)

        assert sync_case == SyncCase.CASE_C_UP_TO_DATE
        assert start_date is None
        assert end_date is None

    @pytest.mark.asyncio
    async def test_analyze_case_c_up_to_date_today(self, service, mock_db):
        """Test Case C: last_saved_date == today → no sync needed"""
        mock_stock = MagicMock()
        mock_stock.id = 1
        mock_stock.symbol = "005930"

        # Last saved date is today (unusual but should be handled)
        today = date.today()

        mock_stock_result = AsyncMock()
        mock_stock_result.scalar_one_or_none.return_value = mock_stock

        mock_price_result = AsyncMock()
        mock_price_result.scalar_one_or_none.return_value = today

        mock_db.execute.side_effect = [mock_stock_result, mock_price_result]

        sync_case, start_date, end_date = await service.analyze_sync_status(stock_id=1)

        assert sync_case == SyncCase.CASE_C_UP_TO_DATE
        assert start_date is None
        assert end_date is None


class TestGapFillingSync:
    """Test Gap Filling sync execution"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return StockDataService(mock_db)

    @pytest.mark.asyncio
    @patch.object(StockDataService, "get_or_create_stock")
    @patch.object(StockDataService, "analyze_sync_status")
    async def test_sync_case_c_returns_early(
        self, mock_analyze, mock_get_stock, service
    ):
        """Test that Case C returns early without fetching data"""
        mock_stock = MagicMock()
        mock_stock.id = 1
        mock_get_stock.return_value = mock_stock

        mock_analyze.return_value = (SyncCase.CASE_C_UP_TO_DATE, None, None)

        result = await service.sync_stock_prices("005930")

        assert result["sync_case"] == "up_to_date"
        assert result["synced_count"] == 0
        assert result["message"] == "Already up to date"

    @pytest.mark.asyncio
    @patch.object(StockDataService, "get_or_create_stock")
    @patch.object(StockDataService, "analyze_sync_status")
    @patch.object(StockDataService, "_update_sync_status")
    @patch.object(StockDataService, "_fetch_historical_prices")
    @patch.object(StockDataService, "_get_exchange_rates_for_dates")
    @patch.object(StockDataService, "_save_prices_batch")
    async def test_sync_case_a_full_collection(
        self,
        mock_save,
        mock_exchange,
        mock_fetch,
        mock_update_status,
        mock_analyze,
        mock_get_stock,
        service,
    ):
        """Test Case A performs full collection from listing date"""
        mock_stock = MagicMock()
        mock_stock.id = 1
        mock_stock.listing_date = date(2020, 1, 15)
        mock_get_stock.return_value = mock_stock

        start_date = date(2020, 1, 15)
        end_date = service._get_yesterday()
        mock_analyze.return_value = (SyncCase.CASE_A_NO_DATA, start_date, end_date)

        # Mock historical data
        mock_fetch.return_value = [
            {"price_date": date(2020, 1, 15), "close_price": Decimal("50000"), "source": "fdr"},
            {"price_date": date(2020, 1, 16), "close_price": Decimal("51000"), "source": "fdr"},
        ]
        mock_exchange.return_value = {}
        mock_save.return_value = 2

        result = await service.sync_stock_prices("005930")

        assert result["sync_case"] == "no_data"
        assert result["synced_count"] == 2
        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(StockDataService, "get_or_create_stock")
    @patch.object(StockDataService, "analyze_sync_status")
    @patch.object(StockDataService, "_update_sync_status")
    @patch.object(StockDataService, "_fetch_historical_prices")
    @patch.object(StockDataService, "_get_exchange_rates_for_dates")
    @patch.object(StockDataService, "_save_prices_batch")
    async def test_sync_case_b_partial_collection(
        self,
        mock_save,
        mock_exchange,
        mock_fetch,
        mock_update_status,
        mock_analyze,
        mock_get_stock,
        service,
    ):
        """Test Case B collects only missing dates (append)"""
        mock_stock = MagicMock()
        mock_stock.id = 1
        mock_get_stock.return_value = mock_stock

        # Gap of 5 days
        last_saved = date.today() - timedelta(days=6)
        gap_start = last_saved + timedelta(days=1)
        end_date = service._get_yesterday()
        mock_analyze.return_value = (SyncCase.CASE_B_GAP_DETECTED, gap_start, end_date)

        # Mock historical data for gap period
        mock_fetch.return_value = [
            {"price_date": gap_start + timedelta(days=i), "close_price": Decimal("50000"), "source": "fdr"}
            for i in range(5)
        ]
        mock_exchange.return_value = {}
        mock_save.return_value = 5

        result = await service.sync_stock_prices("005930")

        assert result["sync_case"] == "gap_detected"
        assert result["synced_count"] == 5
        # Verify fetch was called with gap dates only
        mock_fetch.assert_called_once_with("005930", gap_start, end_date)


class TestBatchOperations:
    """Test batch operations for multiple stocks"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return StockDataService(mock_db)

    @pytest.mark.asyncio
    @patch.object(StockDataService, "_fetch_realtime_from_sources")
    @patch("api.services.stock_service.stock_realtime_cache")
    @patch("api.services.stock_service.exchange_rate_cache")
    async def test_batch_price_fetch_with_cache(
        self,
        mock_exchange_cache,
        mock_stock_cache,
        mock_fetch,
        service,
    ):
        """Test batch price fetching uses cache first"""
        # Setup: One symbol cached, one not
        cached_data = {
            "005930": {
                "symbol": "005930",
                "close_price": "72000.0",
                "open_price": "71000.0",
                "high_price": "73000.0",
                "low_price": "70000.0",
                "volume": 1000000,
                "change": "1000.0",
                "change_percent": "1.41",
                "price_date": "2025-01-21",
                "source": "cache",
                "updated_at": datetime.now().isoformat(),
            },
            "000660": None,  # Not cached
        }
        mock_stock_cache.mget = AsyncMock(return_value=cached_data)
        mock_stock_cache.mset = AsyncMock()

        # Exchange rate for USD conversion
        mock_exchange_cache.get_realtime = AsyncMock(return_value={"rate": "1450.0"})

        # Mock fetch for uncached symbol
        mock_fetch.return_value = {
            "symbol": "000660",
            "close_price": "80000.0",
            "open_price": "79000.0",
            "high_price": "81000.0",
            "low_price": "78000.0",
            "volume": 500000,
            "change": "1000.0",
            "change_percent": "1.27",
            "price_date": "2025-01-21",
            "source": "financedatareader",
            "updated_at": datetime.now().isoformat(),
        }

        results = await service.get_realtime_prices_batch(
            ["005930", "000660"], force_refresh=False
        )

        assert "005930" in results
        assert "000660" in results
        assert results["005930"] is not None
        assert results["000660"] is not None


class TestEnsureDataSynced:
    """Test ensure_data_synced (auto-sync on page access)"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        db.add = MagicMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return StockDataService(mock_db)

    @pytest.mark.asyncio
    @patch.object(StockDataService, "get_stock_by_symbol")
    @patch.object(StockDataService, "analyze_sync_status")
    @patch.object(StockDataService, "get_price_data_summary")
    async def test_ensure_synced_case_c_no_action(
        self, mock_summary, mock_analyze, mock_get_stock, service
    ):
        """Test ensure_data_synced with Case C does not trigger sync"""
        mock_stock = MagicMock()
        mock_stock.id = 1
        mock_get_stock.return_value = mock_stock

        mock_analyze.return_value = (SyncCase.CASE_C_UP_TO_DATE, None, None)
        mock_summary.return_value = {
            "symbol": "005930",
            "stock_id": 1,
            "has_data": True,
            "first_date": "2024-01-01",
            "last_date": (date.today() - timedelta(days=1)).isoformat(),
            "count": 250,
            "listing_date": "2020-01-15",
        }

        result = await service.ensure_data_synced("005930", auto_sync=True)

        assert result["sync_case"] == "up_to_date"
        assert result["needs_sync"] is False
        assert "Data is up to date" in result["message"]

    @pytest.mark.asyncio
    @patch.object(StockDataService, "get_stock_by_symbol")
    @patch.object(StockDataService, "get_or_create_stock")
    @patch.object(StockDataService, "analyze_sync_status")
    @patch.object(StockDataService, "get_price_data_summary")
    @patch.object(StockDataService, "sync_stock_prices")
    async def test_ensure_synced_case_b_auto_sync(
        self, mock_sync, mock_summary, mock_analyze, mock_create, mock_get_stock, service
    ):
        """Test ensure_data_synced with Case B triggers auto-sync"""
        mock_stock = MagicMock()
        mock_stock.id = 1
        mock_get_stock.return_value = mock_stock

        gap_start = date.today() - timedelta(days=5)
        yesterday = date.today() - timedelta(days=1)
        mock_analyze.return_value = (SyncCase.CASE_B_GAP_DETECTED, gap_start, yesterday)

        mock_summary.return_value = {
            "symbol": "005930",
            "stock_id": 1,
            "has_data": True,
            "first_date": "2024-01-01",
            "last_date": (date.today() - timedelta(days=6)).isoformat(),
            "count": 250,
            "listing_date": "2020-01-15",
        }

        mock_sync.return_value = {
            "symbol": "005930",
            "sync_case": "gap_detected",
            "synced_count": 4,
            "start_date": gap_start.isoformat(),
            "end_date": yesterday.isoformat(),
            "source": "financedatareader",
        }

        result = await service.ensure_data_synced("005930", auto_sync=True)

        assert result["sync_case"] == "gap_detected"
        assert result["needs_sync"] is True
        assert result["synced"] is True
        assert result["sync_result"]["synced_count"] == 4
        mock_sync.assert_called_once()

    @pytest.mark.asyncio
    @patch.object(StockDataService, "get_stock_by_symbol")
    @patch.object(StockDataService, "analyze_sync_status")
    @patch.object(StockDataService, "get_price_data_summary")
    async def test_ensure_synced_auto_sync_disabled(
        self, mock_summary, mock_analyze, mock_get_stock, service
    ):
        """Test ensure_data_synced with auto_sync=False does not trigger sync"""
        mock_stock = MagicMock()
        mock_stock.id = 1
        mock_get_stock.return_value = mock_stock

        gap_start = date.today() - timedelta(days=5)
        yesterday = date.today() - timedelta(days=1)
        mock_analyze.return_value = (SyncCase.CASE_B_GAP_DETECTED, gap_start, yesterday)

        mock_summary.return_value = {
            "symbol": "005930",
            "stock_id": 1,
            "has_data": True,
            "first_date": "2024-01-01",
            "last_date": (date.today() - timedelta(days=6)).isoformat(),
            "count": 250,
            "listing_date": "2020-01-15",
        }

        result = await service.ensure_data_synced("005930", auto_sync=False)

        assert result["sync_case"] == "gap_detected"
        assert result["needs_sync"] is True
        assert result["synced"] is False
        assert "Sync needed" in result["message"]


class TestCheckAndReportGaps:
    """Test check_and_report_gaps (dry-run gap analysis)"""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        return db

    @pytest.fixture
    def service(self, mock_db):
        return StockDataService(mock_db)

    @pytest.mark.asyncio
    @patch.object(StockDataService, "get_stock_by_symbol")
    async def test_check_gaps_stock_not_found(self, mock_get_stock, service):
        """Test gap check returns not found for missing stock"""
        mock_get_stock.return_value = None

        result = await service.check_and_report_gaps("INVALID")

        assert result["exists"] is False
        assert "not found" in result["message"]

    @pytest.mark.asyncio
    @patch.object(StockDataService, "get_stock_by_symbol")
    @patch.object(StockDataService, "analyze_sync_status")
    @patch.object(StockDataService, "get_price_data_summary")
    async def test_check_gaps_with_gap(self, mock_summary, mock_analyze, mock_get_stock, service):
        """Test gap check reports gaps correctly"""
        mock_stock = MagicMock()
        mock_stock.id = 1
        mock_get_stock.return_value = mock_stock

        gap_start = date.today() - timedelta(days=30)
        yesterday = date.today() - timedelta(days=1)
        mock_analyze.return_value = (SyncCase.CASE_B_GAP_DETECTED, gap_start, yesterday)

        mock_summary.return_value = {
            "symbol": "005930",
            "stock_id": 1,
            "has_data": True,
            "first_date": "2024-01-01",
            "last_date": (date.today() - timedelta(days=31)).isoformat(),
            "count": 200,
            "listing_date": "2020-01-15",
        }

        result = await service.check_and_report_gaps("005930")

        assert result["exists"] is True
        assert result["sync_case"] == "gap_detected"
        assert result["needs_sync"] is True
        assert result["sync_range"]["start_date"] == gap_start.isoformat()
        assert result["estimated_records"] > 0


class TestExceptions:
    """Test exception handling"""

    def test_stock_data_service_error_hierarchy(self):
        """Test exception inheritance"""
        assert issubclass(StockNotFoundError, StockDataServiceError)
        assert issubclass(StockDataFetchError, StockDataServiceError)

    def test_stock_not_found_error(self):
        """Test StockNotFoundError can be raised"""
        with pytest.raises(StockNotFoundError):
            raise StockNotFoundError("Stock XXXX not found")

    def test_stock_data_fetch_error(self):
        """Test StockDataFetchError can be raised"""
        with pytest.raises(StockDataFetchError):
            raise StockDataFetchError("Failed to fetch from all sources")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
