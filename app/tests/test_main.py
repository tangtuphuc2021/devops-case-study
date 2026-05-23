from fastapi.testclient import TestClient

from src.main import app


client = TestClient(app)


def test_root_contains_service_metadata():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "demo-app"
    assert body["status"] == "ok"


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_metrics_endpoint_exposes_prometheus_metrics():
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "demo_app_http_requests_total" in response.text

