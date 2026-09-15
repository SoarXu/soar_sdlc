from fastapi.testclient import TestClient
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException
import pytest

from app.core.config import settings
from app.core.config import Settings
from app.controllers import health_controller
from app.db.session import get_db


def test_health_endpoint_returns_ok(client: TestClient):
    response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_endpoint_reports_local_version_and_actual_database_revision(client: TestClient):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(text("INSERT INTO alembic_version (version_num) VALUES ('20260910_003')"))

    def version_db():
        with Session(engine) as db:
            yield db

    client.app.dependency_overrides[get_db] = version_db
    try:
        response = client.get("/api/v1/version")
        assert response.status_code == 200
        assert response.json()["app_version"] == "1.0.0"
        assert response.json()["environment"] == "local"
        assert response.json()["database_revision"] == "20260910_003"
    finally:
        client.app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def test_version_does_not_claim_a_revision_when_database_has_no_alembic_table():
    engine = create_engine("sqlite:///:memory:")
    try:
        with Session(engine) as db, pytest.raises(HTTPException) as error:
            health_controller.version_info(db)
        assert error.value.status_code == 503
    finally:
        engine.dispose()


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
