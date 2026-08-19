from app.services import project_permission_service
from app.views.user_view import UserCreate


def test_user_create_only_accepts_system_administrator_flag():
    payload = UserCreate(username="existing-user", full_name="Existing User", is_system_admin=True)

    assert payload.is_system_admin is True
    assert "role_ids" not in UserCreate.model_fields


def test_global_role_scope_contains_only_system_administrator(monkeypatch):
    monkeypatch.setattr(project_permission_service, "is_system_admin", lambda _db, user_id: user_id == 7)

    assert project_permission_service.global_role_keys(object(), 7) == {"system_admin"}
    assert project_permission_service.global_role_keys(object(), 8) == set()
