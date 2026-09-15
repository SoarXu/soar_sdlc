from fastapi.testclient import TestClient
import logging
from fastapi import HTTPException
import pytest

from app.core.config import settings
from app.core.config import Settings
from app.db.session import get_db


def test_health_endpoint_returns_ok(client: TestClient):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_endpoint_reports_only_runtime_version_without_database(client: TestClient):
    def unavailable_db():
        raise HTTPException(status_code=503, detail="test database unavailable")

    client.app.dependency_overrides[get_db] = unavailable_db
    try:
        response = client.get("/api/v1/version")
        assert response.status_code == 200
        assert response.json() == {"app_version": "1.0.0", "environment": "local"}
    finally:
        client.app.dependency_overrides.pop(get_db, None)


def test_production_settings_require_release_build_metadata():
    with pytest.raises(ValueError, match="release metadata"):
        Settings(app_env="production", app_version="1.0.0", git_commit="")


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
