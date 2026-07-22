from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.services import test_run_service
from app.views.test_run_view import TestRunUpdate as UpdatePayload


class _SessionSpy:
    def __init__(self):
        self.rollbacks = 0

    def rollback(self):
        self.rollbacks += 1


def test_stable_test_run_lock_retries_after_iteration_membership_drift(monkeypatch):
    db = _SessionSpy()
    preview_a = SimpleNamespace(id=1, iteration_id=10, project_id=100)
    refreshed_b = SimpleNamespace(id=1, iteration_id=20, project_id=100)
    preview_b = SimpleNamespace(id=1, iteration_id=20, project_id=100)
    calls = iter([preview_a, refreshed_b, preview_b, refreshed_b])
    locked_sets = []

    monkeypatch.setattr(test_run_service, "_get_active_test_run", lambda *_args, **_kwargs: next(calls))
    monkeypatch.setattr(
        test_run_service,
        "lock_iterations_for_mutation",
        lambda _db, ids: (locked_sets.append(set(ids)) or {iteration_id: object() for iteration_id in ids if iteration_id is not None}),
    )

    run, locked_iterations = test_run_service._lock_stable_test_run(db, 1)

    assert run is refreshed_b
    assert set(locked_iterations) == {20}
    assert locked_sets == [{10}, {20}]
    assert db.rollbacks == 1


def test_stable_test_run_lock_rejects_persistent_iteration_membership_drift(monkeypatch):
    db = _SessionSpy()
    calls = iter(
        [
            SimpleNamespace(id=1, iteration_id=10, project_id=100),
            SimpleNamespace(id=1, iteration_id=20, project_id=100),
        ] * test_run_service.TEST_RUN_LOCK_RETRY_LIMIT
    )

    monkeypatch.setattr(test_run_service, "_get_active_test_run", lambda *_args, **_kwargs: next(calls))
    monkeypatch.setattr(test_run_service, "lock_iterations_for_mutation", lambda _db, ids: {iteration_id: object() for iteration_id in ids if iteration_id is not None})

    with pytest.raises(HTTPException) as exc_info:
        test_run_service._lock_stable_test_run(db, 1)

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "ITERATION_STATE_CONFLICT"
    assert db.rollbacks == test_run_service.TEST_RUN_LOCK_RETRY_LIMIT


def test_update_rejects_a_test_run_that_drifted_into_a_terminal_source_iteration(monkeypatch):
    db = _SessionSpy()
    terminal_iteration = SimpleNamespace(id=20, state_category="terminal")
    test_run = SimpleNamespace(id=1, iteration_id=20, project_id=100)

    monkeypatch.setattr(test_run_service, "_lock_stable_test_run", lambda *_args, **_kwargs: (test_run, {20: terminal_iteration}))
    monkeypatch.setattr(test_run_service, "ensure_iteration_mutable", lambda iteration: (_ for _ in ()).throw(HTTPException(status_code=409, detail={"code": "ITERATION_NOT_MUTABLE"})))

    with pytest.raises(HTTPException) as exc_info:
        test_run_service.update_test_run(db, 1, UpdatePayload(name="forbidden"))

    assert exc_info.value.detail["code"] == "ITERATION_NOT_MUTABLE"
