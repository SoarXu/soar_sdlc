from fastapi.testclient import TestClient
import logging

from app.core.config import settings


def test_health_endpoint_returns_ok(client: TestClient):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_slow_api_warning_contains_only_sanitized_metrics(client: TestClient, caplog, monkeypatch):
    assert hasattr(settings, "slow_api_request_ms"), "slow_api_request_ms setting is required"
    monkeypatch.setattr(settings, "slow_api_request_ms", 0)
    caplog.set_level(logging.WARNING)

    response = client.get("/api/v1/projects")

    assert response.status_code == 200
    records = [record for record in caplog.records if record.getMessage() == "slow_api_request"]
    assert records
    record = records[-1]
    assert record.method == "GET"
    assert record.path == "/api/v1/projects"
    assert record.status_code == 200
    assert record.query_count > 0
    assert record.database_time_ms >= 0
    assert "SELECT" not in record.getMessage()
