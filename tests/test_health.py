import pytest
import httpx
import sys
import os
from fastapi.testclient import TestClient

# Add the app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'app'))

from main import app

client = TestClient(app)

class TestHealth:
    def test_basic_health(self):
        """Test basic health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data

    def test_detailed_health(self):
        """Test detailed health endpoint"""
        response = client.get("/health/detailed")
        # This might fail if database is not available
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "healthy"
            assert "services" in data
            assert "database" in data["services"]
            assert "application" in data["services"]

    def test_root_endpoint(self):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert "docs" in data

    def test_openapi_schema(self):
        """Test OpenAPI schema is available"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "info" in data

    def test_docs_endpoint(self):
        """Test documentation endpoint"""
        response = client.get("/docs")
        assert response.status_code == 200
