"""
Tests for FastAPI service
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'code_source'))
os.environ['MODEL_FILE'] = os.path.join(os.path.dirname(__file__), '..', 'modeles', 'hybrid_model.pkl')

import pytest
from fastapi.testclient import TestClient
from src.service import app


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


def test_health_endpoint(client):
    """Test health check"""
    response = client.get("/health")
    assert response.status_code == 200
    assert "status" in response.json()


def test_metrics_endpoint(client):
    """Test Prometheus metrics"""
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "predictions_total" in response.text


def test_root_endpoint(client):
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert "service" in response.json()
    assert response.json()["service"] == "Anomaly Detection"
