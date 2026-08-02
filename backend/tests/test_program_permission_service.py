from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.program import Program
from app.models.project import Project
from app.models.role import Role, UserRole
from app.models.user import User
from app.models.workflow_definition import WorkflowState
from app.services.program_permission_service import (
    can_create_child_program,
    can_delete_program,
    can_manage_program,
    is_program_governor,
)


@pytest.fixture(autouse=True)
def _cleanup_program_permission_rows():
    db = SessionLocal()
    try:
        existing_user_ids = {user_id for (user_id,) in db.query(User.id).all()}
        existing_program_ids = {program_id for (program_id,) in db.query(Program.id).all()}
        existing_project_ids = {project_id for (project_id,) in db.query(Project.id).all()}
        existing_role_ids = {role_id for (role_id,) in db.query(Role.id).all()}
    finally:
        db.close()

    yield

    db = SessionLocal()
    try:
        created_program_ids = {
            program_id
            for (program_id,) in db.query(Program.id).all()
            if program_id not in existing_program_ids
        }
        created_user_ids = {
            user_id
            for (user_id,) in db.query(User.id).all()
            if user_id not in existing_user_ids
        }
        created_project_ids = {
            project_id
            for (project_id,) in db.query(Project.id).all()
            if project_id not in existing_project_ids
        }
        created_role_ids = {
            role_id
            for (role_id,) in db.query(Role.id).all()
            if role_id not in existing_role_ids
        }
        if created_project_ids:
            db.query(Project).filter(Project.id.in_(created_project_ids)).delete(synchronize_session=False)
        if created_program_ids:
            db.query(Program).filter(Program.id.in_(created_program_ids)).delete(synchronize_session=False)
        if created_user_ids:
            db.query(UserRole).filter(UserRole.user_id.in_(created_user_ids)).delete(synchronize_session=False)
            db.query(User).filter(User.id.in_(created_user_ids)).delete(synchronize_session=False)
        if created_role_ids:
            db.query(UserRole).filter(UserRole.role_id.in_(created_role_ids)).delete(synchronize_session=False)
            db.query(Role).filter(Role.id.in_(created_role_ids)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _create_user(*, system_admin: bool = False) -> User:
    db = SessionLocal()
    try:
        user = User(
            username=f"program_permission_{uuid4().hex[:8]}",
            full_name="Program Permission User",
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        if system_admin:
            role = db.query(Role).filter(Role.role_key == "system_admin").first()
            if not role:
                role = Role(role_key="system_admin", role_name="system_admin", enabled=True, is_system=True)
                db.add(role)
                db.flush()
            db.add(UserRole(user_id=user.id, role_id=role.id))
        db.commit()
        db.refresh(user)
        return user
    finally:
        db.close()


def _create_program(
    *,
    owner_id: int | None,
    parent_id: int | None = None,
    deleted: int = 0,
    status: str = "planning",
) -> Program:
    db = SessionLocal()
    try:
        program = Program(
            name=f"Program Permission {uuid4().hex[:8]}",
            owner_id=owner_id,
            parent_id=parent_id,
            deleted=deleted,
            status=status,
        )
        db.add(program)
        db.commit()
        db.refresh(program)
        return program
    finally:
        db.close()


def _is_program_governor(program_id: int, actor_id: int) -> bool:
    db = SessionLocal()
    try:
        return is_program_governor(db, program_id, actor_id)
    finally:
        db.close()


def _create_project(*, program_id: int, terminal: bool) -> Project:
    db = SessionLocal()
    try:
        state = (
            db.query(WorkflowState)
            .filter(WorkflowState.category == ("terminal" if terminal else "start"))
            .first()
        )
        assert state is not None, "The default workflow must provide the requested project state"
        project = Project(
            name=f"Program Permission Project {uuid4().hex[:8]}",
            program_id=program_id,
            workflow_definition_id=state.definition_id,
            current_state_id=state.id,
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project
    finally:
        db.close()


def _program_permission(predicate, program_id: int, actor_id: int) -> bool:
    db = SessionLocal()
    try:
        return predicate(db, program_id, actor_id)
    finally:
        db.close()


def test_program_owner_governs_owned_program_and_all_active_descendants():
    owner = _create_user()
    child_owner = _create_user()
    grandchild_owner = _create_user()
    root = _create_program(owner_id=owner.id)
    child = _create_program(owner_id=child_owner.id, parent_id=root.id)
    grandchild = _create_program(owner_id=grandchild_owner.id, parent_id=child.id)

    assert _is_program_governor(root.id, owner.id) is True
    assert _is_program_governor(child.id, owner.id) is True
    assert _is_program_governor(grandchild.id, owner.id) is True


def test_child_owner_cannot_govern_parent_or_sibling_program():
    root_owner = _create_user()
    child_owner = _create_user()
    root = _create_program(owner_id=root_owner.id)
    child = _create_program(owner_id=child_owner.id, parent_id=root.id)
    sibling = _create_program(owner_id=None, parent_id=root.id)

    assert _is_program_governor(child.id, child_owner.id) is True
    assert _is_program_governor(root.id, child_owner.id) is False
    assert _is_program_governor(sibling.id, child_owner.id) is False


def test_system_administrator_governs_every_program():
    administrator = _create_user(system_admin=True)
    owner = _create_user()
    root = _create_program(owner_id=owner.id)
    child = _create_program(owner_id=None, parent_id=root.id)

    assert _is_program_governor(root.id, administrator.id) is True
    assert _is_program_governor(child.id, administrator.id) is True


def test_owner_transfer_immediately_removes_former_owners_derived_authority():
    former_owner = _create_user()
    replacement_owner = _create_user()
    root = _create_program(owner_id=former_owner.id)
    child = _create_program(owner_id=None, parent_id=root.id)

    assert _is_program_governor(child.id, former_owner.id) is True

    db = SessionLocal()
    try:
        db.query(Program).filter(Program.id == root.id).update({"owner_id": replacement_owner.id})
        db.commit()
    finally:
        db.close()

    assert _is_program_governor(child.id, former_owner.id) is False
    assert _is_program_governor(child.id, replacement_owner.id) is True


def test_deleted_program_never_confers_governance_authority():
    owner = _create_user()
    deleted_root = _create_program(owner_id=owner.id, deleted=1)
    active_child = _create_program(owner_id=None, parent_id=deleted_root.id)

    assert _is_program_governor(deleted_root.id, owner.id) is False
    assert _is_program_governor(active_child.id, owner.id) is False


def test_parent_cycle_raises_clear_conflict_instead_of_looping():
    owner = _create_user()
    root = _create_program(owner_id=owner.id)
    child = _create_program(owner_id=None, parent_id=root.id)

    db = SessionLocal()
    try:
        db.query(Program).filter(Program.id == root.id).update({"parent_id": child.id})
        db.commit()
    finally:
        db.close()

    with pytest.raises(HTTPException, match="cycle") as exc_info:
        _is_program_governor(child.id, owner.id)

    assert exc_info.value.status_code == 409


def test_disabled_or_deleted_users_cannot_govern_even_with_owner_or_admin_roles():
    disabled_owner = _create_user()
    deleted_owner = _create_user()
    disabled_admin = _create_user(system_admin=True)
    disabled_owner_program = _create_program(owner_id=disabled_owner.id)
    deleted_owner_program = _create_program(owner_id=deleted_owner.id)
    other_program = _create_program(owner_id=None)

    db = SessionLocal()
    try:
        db.query(User).filter(User.id == disabled_owner.id).update({"is_active": False})
        db.query(User).filter(User.id == deleted_owner.id).update({"deleted": 1})
        db.query(User).filter(User.id == disabled_admin.id).update({"is_active": False})
        db.commit()
    finally:
        db.close()

    assert _is_program_governor(disabled_owner_program.id, disabled_owner.id) is False
    assert _is_program_governor(deleted_owner_program.id, deleted_owner.id) is False
    assert _is_program_governor(other_program.id, disabled_admin.id) is False


def test_create_child_and_manage_helpers_follow_program_governance():
    owner = _create_user()
    unrelated = _create_user()
    root = _create_program(owner_id=owner.id)
    child = _create_program(owner_id=None, parent_id=root.id)

    assert _program_permission(can_create_child_program, root.id, owner.id) is True
    assert _program_permission(can_manage_program, child.id, owner.id) is True
    assert _program_permission(can_create_child_program, root.id, unrelated.id) is False
    assert _program_permission(can_manage_program, child.id, unrelated.id) is False


def test_program_owner_can_delete_nonempty_tree_regardless_of_lifecycle_state():
    owner = _create_user()
    empty_program = _create_program(owner_id=owner.id)
    root = _create_program(owner_id=owner.id, status="planning")
    child = _create_program(owner_id=None, parent_id=root.id, status="active")
    _create_project(program_id=child.id, terminal=False)

    assert _program_permission(can_delete_program, empty_program.id, owner.id) is True
    assert _program_permission(can_delete_program, root.id, owner.id) is True


def test_system_admin_can_delete_nonempty_tree_regardless_of_lifecycle_state():
    administrator = _create_user(system_admin=True)
    root = _create_program(owner_id=None, status="closed")
    child = _create_program(owner_id=None, parent_id=root.id, status="closed")
    project = _create_project(program_id=child.id, terminal=True)

    assert _program_permission(can_delete_program, root.id, administrator.id) is True

    db = SessionLocal()
    try:
        db.query(Program).filter(Program.id == child.id).update({"status": "active"})
        db.commit()
    finally:
        db.close()
    assert _program_permission(can_delete_program, root.id, administrator.id) is True

    db = SessionLocal()
    try:
        non_terminal_state = db.query(WorkflowState).filter(WorkflowState.category == "start").first()
        assert non_terminal_state is not None
        db.query(Program).filter(Program.id == child.id).update({"status": "closed"})
        db.query(Project).filter(Project.id == project.id).update({"current_state_id": non_terminal_state.id})
        db.commit()
    finally:
        db.close()
    assert _program_permission(can_delete_program, root.id, administrator.id) is True


def test_admin_tree_delete_uses_batched_subtree_queries_for_wide_tree():
    administrator = _create_user(system_admin=True)
    root = _create_program(owner_id=None, status="closed")
    children = [
        _create_program(owner_id=None, parent_id=root.id, status="closed")
        for _ in range(4)
    ]
    for child in children:
        for _ in range(4):
            _create_program(owner_id=None, parent_id=child.id, status="closed")

    select_statements: list[str] = []

    def _record_select(_conn, _cursor, statement, _parameters, _context, _executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            select_statements.append(statement)

    db = SessionLocal()
    event.listen(db.bind, "before_cursor_execute", _record_select)
    try:
        assert can_delete_program(db, root.id, administrator.id) is True
    finally:
        event.remove(db.bind, "before_cursor_execute", _record_select)
        db.close()

    assert len(select_statements) <= 10
