"""Test configuration and fixtures."""
import os
import pytest
from fastapi.testclient import TestClient

# Force mock mode for tests
os.environ["USE_MOCK"] = "true"

from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_stock_code():
    """Sample stock code for testing."""
    return "005930"  # Samsung Electronics


@pytest.fixture
def mock_date_range():
    """Sample date range for testing."""
    return {
        "start": "2024-01-01",
        "end": "2024-12-31",
    }
