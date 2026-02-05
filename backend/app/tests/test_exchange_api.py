"""Exchange rate API tests."""
import pytest


class TestExchangeAPI:
    """Test exchange rate endpoints."""
    
    def test_get_current_rate(self, client):
        """Test current exchange rate endpoint."""
        response = client.get("/api/exchange/current")
        assert response.status_code == 200
        
        data = response.json()
        assert "rate" in data
        assert "date" in data
        assert "change" in data
        assert "change_percent" in data
        
        # Rate should be realistic KRW/USD value
        assert 1000 < data["rate"] < 2000
    
    def test_get_exchange_history(self, client, mock_date_range):
        """Test exchange rate history endpoint."""
        response = client.get(
            "/api/exchange/history",
            params={"start": mock_date_range["start"], "end": mock_date_range["end"]}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "data" in data
        assert "count" in data
        assert len(data["data"]) > 0
        
        # Check data structure
        first_item = data["data"][0]
        assert "date" in first_item
        assert "open" in first_item
        assert "high" in first_item
        assert "low" in first_item
        assert "close" in first_item
    
    def test_get_exchange_history_missing_start(self, client):
        """Test exchange history without required start parameter."""
        response = client.get("/api/exchange/history")
        assert response.status_code == 422  # Validation error
    
    def test_get_exchange_history_only_start(self, client, mock_date_range):
        """Test exchange history with only start date (end defaults to today)."""
        response = client.get(
            "/api/exchange/history",
            params={"start": mock_date_range["start"]}
        )
        assert response.status_code == 200
        
        data = response.json()
        assert "data" in data
        assert len(data["data"]) > 0
