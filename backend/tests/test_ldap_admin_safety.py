from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import User


def _admin(user_id: int, username: str) -> User:
    return User(
        id=user_id,
        username=username,
        full_name=username,
        password_hash=get_password_hash("local-password"),
        auth_source="local",
        is_active=True,
        is_system_admin=True,
        must_change_password=False,
        deleted=0,
    )


def test_last_local_admin_cannot_be_bound_to_ldap():
    from app.services.ldap_sync_service import SyncItemError, _apply_decision

    engine = create_engine("sqlite:///:memory:")
    User.__table__.create(engine)
    with Session(engine) as db:
        user = _admin(1, "only-admin")
        db.add(user)
        db.commit()
        entry = {
            "username": user.username,
            "employee_no": None,
            "full_name": user.full_name,
            "email": None,
            "mobile": None,
            "department": None,
            "external_id": str(uuid4()),
            "dn": "CN=only-admin,DC=example,DC=com",
            "enabled": True,
        }

        with pytest.raises(SyncItemError, match="本地系统管理员") as error:
            _apply_decision(db, entry, "bind", user.id)
        assert error.value.code == "LOCAL_ADMIN_REQUIRED"


def test_last_local_admin_cannot_lose_system_admin_permission():
    from app.services.role_service import set_user_system_admin

    engine = create_engine("sqlite:///:memory:")
    User.__table__.create(engine)
    with Session(engine) as db:
        first = _admin(1, "first-admin")
        db.add(first)
        db.commit()

        with pytest.raises(HTTPException) as error:
            set_user_system_admin(db, first.id, False)
        assert error.value.detail["code"] == "LOCAL_ADMIN_REQUIRED"

        db.add(_admin(2, "second-admin"))
        db.commit()
        assert set_user_system_admin(db, first.id, False).is_system_admin is False
