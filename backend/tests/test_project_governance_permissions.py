from types import SimpleNamespace

from app.controllers import project_controller
from app.services import project_permission_service
from app.views.project_view import ProjectCreate


def test_any_authenticated_user_can_create_project(monkeypatch):
    actor = SimpleNamespace(id=7)
    monkeypatch.setattr(project_permission_service, "is_system_admin", lambda *_args: False)

    assert project_permission_service.can_create_project(SimpleNamespace(), None, actor) is True


def test_project_controller_defaults_owner_to_creator_and_preserves_explicit_owner(monkeypatch):
    creator = SimpleNamespace(id=7)
    captured_payloads = []
    monkeypatch.setattr(project_controller, "ensure_authenticated", lambda *_args: None)
    monkeypatch.setattr(project_controller, "resolve_project_create_payload", lambda _db, payload: payload)
    monkeypatch.setattr(project_controller, "ensure_project_create_permission", lambda *_args: None)
    monkeypatch.setattr(
        project_controller,
        "create_project",
        lambda _db, payload: captured_payloads.append(payload) or payload,
    )

    project_controller.post_project(ProjectCreate(name="Default owner"), SimpleNamespace(), creator)
    project_controller.post_project(ProjectCreate(name="Explicit owner", owner_id=9), SimpleNamespace(), creator)

    assert [payload.owner_id for payload in captured_payloads] == [7, 9]


def test_project_governance_allows_project_owner_ancestor_and_program_governor(monkeypatch):
    actor = SimpleNamespace(id=7)
    project = SimpleNamespace(id=12, program_id=4)
    monkeypatch.setattr(project_permission_service, "can_manage_project", lambda *_args: False)
    monkeypatch.setattr(project_permission_service, "is_system_admin", lambda *_args: False)
    monkeypatch.setattr(project_permission_service, "_get_active_project", lambda *_args: project)
    monkeypatch.setattr(project_permission_service, "is_program_governor", lambda *_args: False)
    monkeypatch.setattr(project_permission_service, "_is_project_owner_ancestor", lambda *_args: True, raising=False)

    assert project_permission_service.can_govern_project(SimpleNamespace(), project.id, actor) is True

    monkeypatch.setattr(project_permission_service, "_is_project_owner_ancestor", lambda *_args: False)
    monkeypatch.setattr(project_permission_service, "is_program_governor", lambda *_args: True)
    assert project_permission_service.can_govern_project(SimpleNamespace(), project.id, actor) is True


def test_project_configuration_and_deletion_use_project_governance(monkeypatch):
    actor = SimpleNamespace(id=7)
    monkeypatch.setattr(project_permission_service, "can_manage_project", lambda *_args: False)
    monkeypatch.setattr(project_permission_service, "can_govern_project", lambda *_args: True)
    monkeypatch.setattr(project_permission_service, "is_system_admin", lambda *_args: False)
    monkeypatch.setattr(project_permission_service, "_has_active_project_children_or_work_items", lambda *_args: False)

    project_permission_service.ensure_project_manage_permission(SimpleNamespace(), 12, actor)
    project_permission_service.ensure_project_delete_permission(SimpleNamespace(), 12, actor)


def test_non_admin_governor_can_delete_only_an_empty_leaf_project(monkeypatch):
    actor = SimpleNamespace(id=7)
    monkeypatch.setattr(project_permission_service, "can_govern_project", lambda *_args: True)
    monkeypatch.setattr(project_permission_service, "is_system_admin", lambda *_args: False)
    monkeypatch.setattr(
        project_permission_service,
        "_has_active_project_children_or_work_items",
        lambda *_args: True,
        raising=False,
    )

    assert project_permission_service.can_delete_project(SimpleNamespace(), 12, actor) is False

    monkeypatch.setattr(project_permission_service, "is_system_admin", lambda *_args: True)
    assert project_permission_service.can_delete_project(SimpleNamespace(), 12, actor) is True
