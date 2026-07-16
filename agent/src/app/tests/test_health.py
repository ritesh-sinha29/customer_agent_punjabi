from unittest.mock import patch

from fastapi.testclient import TestClient

from src.app.main import app

client = TestClient(app)


def test_health_endpoint_healthy():
    """Verify health endpoint returns status healthy when services are connected."""
    with (
        patch("src.app.main.pinecone_service.check_connection", return_value=True),
        patch("src.app.main.llama_service.check_connection", return_value=True),
    ):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["details"]["pinecone"] == "connected"
        assert data["details"]["llama_cloud"] == "connected"


def test_health_endpoint_degraded():
    """Verify health endpoint returns status degraded when a service is disconnected."""
    with (
        patch("src.app.main.pinecone_service.check_connection", return_value=False),
        patch("src.app.main.llama_service.check_connection", return_value=True),
    ):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "degraded"
        assert data["details"]["pinecone"] == "disconnected"
        assert data["details"]["llama_cloud"] == "connected"
