"""Health check API tests."""
import pytest


class TestHealthAPI:
    """Test health check endpoints."""
    
    def test_health_check(self, client):
        """Test health check endpoint returns 200."""
        response = client.get("/api/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert "app_name" in data
        assert "version" in data
        assert "mock_mode" in data
    
    def test_root_endpoint(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")
        assert response.status_code == 200
        
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data
