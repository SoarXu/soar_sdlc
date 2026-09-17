from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User


def _user(**overrides):
    suffix = uuid4().hex[:10]
    data = {
        "username": f"ldap_match_{suffix}",
        "full_name": "Existing User",
        "email": f"{suffix}@example.com",
        "password_hash": get_password_hash("test-only-password"),
        "department": "Test",
        "is_active": True,
        "must_change_password": False,
        "deleted": 0,
    }
    data.update(overrides)
    return User(**data)


def _entry(**overrides):
    data = {
        "username": f"ad_{uuid4().hex[:10]}",
        "employee_no": None,
        "full_name": "AD User",
        "email": None,
        "mobile": None,
        "department": "R&D",
        "external_id": str(uuid4()),
        "dn": "CN=AD User,DC=example,DC=com",
        "enabled": True,
    }
    data.update(overrides)
    return data


def test_match_prefers_existing_external_id_over_other_identity_signals():
    from app.services.ldap_sync_service import match_directory_user

    db = SessionLocal()
    linked = _user(ldap_external_id=str(uuid4()), auth_source="ldap")
    other = _user(employee_no=f"E-{uuid4().hex[:8]}")
    db.add_all([linked, other])
    db.commit()
    try:
        result = match_directory_user(
            db,
            _entry(
                external_id=linked.ldap_external_id,
                employee_no=other.employee_no,
                username=other.username,
            ),
        )
        assert result["sync_status"] == "linked"
        assert result["matched_user"]["id"] == linked.id
        assert result["conflict_reason"] is None
    finally:
        db.delete(linked)
        db.delete(other)
        db.commit()
        db.close()


def test_match_reports_conflict_when_employee_number_and_email_hit_different_users():
    from app.services.ldap_sync_service import match_directory_user

    db = SessionLocal()
    employee_user = _user(employee_no=f"E-{uuid4().hex[:8]}")
    email_user = _user()
    db.add_all([employee_user, email_user])
    db.commit()
    try:
        result = match_directory_user(
            db,
            _entry(employee_no=employee_user.employee_no, email=email_user.email),
        )
        assert result["sync_status"] == "conflict"
        assert result["matched_user"] is None
        assert "不同用户" in result["conflict_reason"]
    finally:
        db.delete(employee_user)
        db.delete(email_user)
        db.commit()
        db.close()


def test_disabled_directory_user_is_marked_without_changing_local_user():
    from app.services.ldap_sync_service import match_directory_user

    db = SessionLocal()
    linked = _user(ldap_external_id=str(uuid4()), auth_source="ldap")
    db.add(linked)
    db.commit()
    try:
        result = match_directory_user(db, _entry(external_id=linked.ldap_external_id, enabled=False))
        assert result["sync_status"] == "ad_disabled"
        assert result["matched_user"]["id"] == linked.id
        db.refresh(linked)
        assert linked.is_active is True
    finally:
        db.delete(linked)
        db.commit()
        db.close()


def test_username_and_email_matching_is_case_insensitive():
    from app.services.ldap_sync_service import match_directory_user

    db = SessionLocal()
    existing = _user()
    db.add(existing)
    db.commit()
    try:
        result = match_directory_user(
            db,
            _entry(username=existing.username.upper(), email=existing.email.upper()),
        )
        assert result["sync_status"] == "match_suggested"
        assert result["matched_user"]["id"] == existing.id
    finally:
        db.delete(existing)
        db.commit()
        db.close()


def test_case_insensitive_identity_matching_is_applied_in_database_query():
    from app.services.ldap_sync_service import match_directory_user

    engine = create_engine("sqlite:///:memory:")
    User.__table__.create(engine)
    with Session(engine) as db:
        existing = _user(id=1, username="CaseSensitive", email="Case@Example.com")
        db.add(existing)
        db.commit()

        result = match_directory_user(
            db,
            _entry(username="casesensitive", email="case@example.com"),
        )

        assert result["sync_status"] == "match_suggested"
        assert result["matched_user"]["id"] == existing.id


def test_fallback_match_conflicts_when_candidate_has_another_ldap_identity():
    from app.services.ldap_sync_service import match_directory_user

    db = SessionLocal()
    existing = _user(
        employee_no=f"E-{uuid4().hex[:8]}",
        ldap_external_id=str(uuid4()),
        auth_source="ldap",
    )
    db.add(existing)
    db.commit()
    try:
        result = match_directory_user(
            db,
            _entry(external_id=str(uuid4()), employee_no=existing.employee_no),
        )
        assert result["sync_status"] == "conflict"
        assert result["matched_user"] is None
        assert "其他 AD 身份" in result["conflict_reason"]
    finally:
        db.delete(existing)
        db.commit()
        db.close()
