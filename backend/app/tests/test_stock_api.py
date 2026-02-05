"""Stock API tests."""
import pytest


class TestStockSearchAPI:
    """Test stock search endpoints."""
    
    def test_search_stocks_by_name(self, client):
        """Test stock search by Korean name."""
        response = client.get("/api/stocks/search", params={"q": "삼성"})
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        assert "count" in data
        assert len(data["results"]) > 0
        
        # Check result structure
        first_result = data["results"][0]
        assert "code" in first_result
        assert "name" in first_result
        assert "market" in first_result
        assert "삼성" in first_result["name"]
    
    def test_search_stocks_by_code(self, client, mock_stock_code):
        """Test stock search by code."""
        response = client.get("/api/stocks/search", params={"q": mock_stock_code})
        assert response.status_code == 200
        
        data = response.json()
        assert "results" in data
        assert len(data["results"]) > 0
    
    def test_search_stocks_with_limit(self, client):
        """Test stock search with limit parameter."""
        response = client.get("/api/stocks/search", params={"q": "삼성", "limit": 5})
        assert response.status_code == 200
        
        data = response.json()
        assert len(data["results"]) <= 5
    
    def test_search_stocks_missing_query(self, client):
        """Test stock search without query parameter."""
        response = client.get("/api/stocks/search")
        assert response.status_code == 422  # Validation error


class TestPopularStocksAPI:
    """Test popular stocks endpoint."""
    
    def test_get_popular_stocks(self, client):
        """Test popular stocks endpoint."""
        response = client.get("/api/stocks/popular")
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Check structure
        first_stock = data[0]
        assert "code" in first_stock
        assert "name" in first_stock
        assert "price" in first_stock
    
    def test_get_popular_stocks_with_limit(self, client):
        """Test popular stocks with limit."""
        response = client.get("/api/stocks/popular", params={"limit": 5})
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) <= 5


class TestStockInfoAPI:
    """Test stock info endpoint."""
    
    def test_get_stock_info(self, client, mock_stock_code):
        """Test stock info endpoint."""
        response = client.get(f"/api/stocks/{mock_stock_code}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["code"] == mock_stock_code
        assert "name" in data
        assert "market" in data
        assert "price" in data
        assert "change" in data
        assert "change_percent" in data
        assert "volume" in data
    
    def test_get_stock_info_not_found(self, client):
        """Test stock info with invalid code."""
        response = client.get("/api/stocks/INVALID")
        assert response.status_code == 404


class TestStockHistoryAPI:
    """Test stock history endpoint."""
    
    def test_get_stock_history(self, client, mock_stock_code, mock_date_range):
        """Test stock history endpoint."""
        response = client.get(
            f"/api/stocks/{mock_stock_code}/history",
            params={"start": mock_date_range["start"], "end": mock_date_range["end"]}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Check OHLCV structure
        first_item = data[0]
        assert "date" in first_item
        assert "open" in first_item
        assert "high" in first_item
        assert "low" in first_item
        assert "close" in first_item
        assert "volume" in first_item
    
    def test_get_stock_history_missing_start(self, client, mock_stock_code):
        """Test stock history without start date."""
        response = client.get(f"/api/stocks/{mock_stock_code}/history")
        assert response.status_code == 422


class TestStockUsdAPI:
    """Test USD conversion API - 핵심 기능."""
    
    def test_get_stock_usd_history(self, client, mock_stock_code, mock_date_range):
        """Test USD converted stock history - 핵심 API 테스트."""
        response = client.get(
            f"/api/stocks/{mock_stock_code}/usd",
            params={"start": mock_date_range["start"], "end": mock_date_range["end"]}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert data["code"] == mock_stock_code
        assert "name" in data
        assert "data" in data
        assert "count" in data
        assert len(data["data"]) > 0
        
        # Check USD conversion structure - 핵심 데이터 검증
        first_item = data["data"][0]
        assert "date" in first_item
        assert "krw_close" in first_item
        assert "exchange_rate" in first_item
        assert "usd_close" in first_item
        
        # Verify USD calculation: usd_close ≈ krw_close / exchange_rate
        expected_usd = first_item["krw_close"] / first_item["exchange_rate"]
        assert abs(first_item["usd_close"] - expected_usd) < 0.01
    
    def test_get_stock_usd_current(self, client, mock_stock_code):
        """Test current USD price endpoint."""
        response = client.get(f"/api/stocks/{mock_stock_code}/usd/current")
        assert response.status_code == 200
        
        data = response.json()
        assert data["code"] == mock_stock_code
        assert "name" in data
        assert "krw_price" in data
        assert "exchange_rate" in data
        assert "usd_price" in data
        
        # Verify calculation
        expected_usd = data["krw_price"] / data["exchange_rate"]
        assert abs(data["usd_price"] - expected_usd) < 0.01
    
    def test_get_stock_usd_not_found(self, client, mock_date_range):
        """Test USD history with invalid code."""
        response = client.get(
            "/api/stocks/INVALID/usd",
            params={"start": mock_date_range["start"]}
        )
        assert response.status_code == 404
