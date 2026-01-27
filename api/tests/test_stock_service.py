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

    @pytest.mark.asyncio
    async def test_analyze_sync_status_case_a_no_data(self, service, mock_db):
        """Test Case A: No data exists - should return full collection range"""
        # Mock: No existing prices
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        sync_case, start_date, end_date = await service.analyze_sync_status(
            stock_id=1
        )

        assert sync_case == SyncCase.CASE_A_NO_DATA
        assert start_date is not None
        assert end_date == date.today()
        # Start date should be 365 days ago (default)
        expected_start = date.today() - timedelta(days=365)
        assert start_date == expected_start

    @pytest.mark.asyncio
    async def test_analyze_sync_status_case_b_gap_detected(self, service, mock_db):
        """Test Case B: Gap detected - should return gap range"""
        # Mock: Last price is 5 days ago
        last_price_date = date.today() - timedelta(days=5)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = last_price_date
        mock_db.execute.return_value = mock_result

        sync_case, start_date, end_date = await service.analyze_sync_status(
            stock_id=1
        )

        assert sync_case == SyncCase.CASE_B_GAP_DETECTED
        assert start_date == last_price_date + timedelta(days=1)
        assert end_date == date.today()

    @pytest.mark.asyncio
    async def test_analyze_sync_status_case_c_up_to_date(self, service, mock_db):
        """Test Case C: Data is up to date - should return no action needed"""
        # Mock: Last price is today or yesterday
        last_price_date = date.today() - timedelta(days=1)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none.return_value = last_price_date
        mock_db.execute.return_value = mock_result

        sync_case, start_date, end_date = await service.analyze_sync_status(
            stock_id=1
        )

        assert sync_case == SyncCase.CASE_C_UP_TO_DATE
        assert start_date is None
        assert end_date is None


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


class TestGapFillingSync:
    """Test Gap Filling sync strategy"""

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
