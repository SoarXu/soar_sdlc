from types import SimpleNamespace

from app.db.session import SessionLocal
from app.services.status_operation_service import create_status_operation


def test_create_status_operation_accepts_legacy_payload_without_delegate_reason(client):
    db_session = SessionLocal()
    payload = SimpleNamespace(effective_time=None, reason=None, remark="legacy")

    try:
        operation = create_status_operation(
            db_session,
            object_type="bug",
            object_id=1,
            action="start_fixing",
            from_status="open",
            to_status="fixing",
            payload=payload,
        )

        assert operation.delegate_reason is None
        assert operation.remark == "legacy"
    finally:
        db_session.rollback()
        db_session.close()


def test_create_status_operation_persists_runtime_resolution_metadata(client):
    db_session = SessionLocal()
    payload = SimpleNamespace(
        effective_time=None,
        reason=None,
        remark="runtime",
        delegate_reason=None,
        selected_values={"bug_type": "code_issue"},
        default_target_status="fixing",
        resolved_target_status="pending_verification",
        override_reason="manual exception",
    )

    try:
        operation = create_status_operation(
            db_session,
            object_type="bug",
            object_id=1,
            action="confirm_bug_type",
            from_status="pending_handling",
            to_status="pending_verification",
            payload=payload,
        )

        assert operation.selected_values == {"bug_type": "code_issue"}
        assert operation.default_target_status == "fixing"
        assert operation.resolved_target_status == "pending_verification"
        assert operation.override_reason == "manual exception"
    finally:
        db_session.rollback()
        db_session.close()
