# Project and Program Management Permission Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow owners to edit and transition their projects and programs, let program ownership inherit through descendant nodes, and restrict owner deletion to empty leaf nodes.

**Architecture:** Extend the existing project permission service with program-tree ownership predicates, then make both controllers use those predicates for mutation endpoints. Keep the system-administrator override and existing cascade-delete service behavior, but only allow that cascade when the caller is a system administrator.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3.

---

### Task 1: Specify the authorization matrix with failing API tests

**Files:**
- Modify: `backend/tests/test_project_permission_boundary_api.py`

**Step 1: Write failing tests for project ownership and inherited program ownership**

Use the existing `_create_user` and `_auth` helpers. Create a user with no system role, a separate unrelated user, a root program owned by the first user, a child program, and a project assigned to the child program. Assert the root program owner can PATCH and start the descendants, and the unrelated user receives `403` for the same actions.

```python
def test_program_owner_manages_descendant_program_and_project(client: TestClient):
    owner_id, owner_token = _create_user("Tree Owner")
    _, other_token = _create_user("Unrelated User")
    root = client.post("/api/v1/programs", json={"name": "Root", "owner_id": owner_id}).json()
    child = client.post("/api/v1/programs", json={"name": "Child", "parent_id": root["id"]}).json()
    project = client.post("/api/v1/projects", json={"name": "Project", "program_id": child["id"]}).json()

    assert client.patch(f"/api/v1/programs/{child['id']}", json={"description": "owned"}, headers=_auth(owner_token)).status_code == 200
    assert client.patch(f"/api/v1/projects/{project['id']}", json={"description": "owned"}, headers=_auth(owner_token)).status_code == 200
    assert client.patch(f"/api/v1/programs/{child['id']}", json={"description": "denied"}, headers=_auth(other_token)).status_code == 403
    assert client.patch(f"/api/v1/projects/{project['id']}", json={"description": "denied"}, headers=_auth(other_token)).status_code == 403
```

Add equivalent assertions for `start`, with required effective-time payloads, for both child program and project.

**Step 2: Write failing tests for owner leaf-only deletion**

Create an owned leaf project and an owned project with a child. Assert the owner receives `204` for the leaf and `403` for the parent. Repeat with an owned leaf program and a program containing a descendant; then assert an administrator can still delete the non-leaf program.

**Step 3: Run the tests to verify they fail**

Run: `pytest backend/tests/test_project_permission_boundary_api.py -v`

Expected: FAIL because program mutation endpoints require `system_admin`, project ownership does not inherit from programs, and project deletion is administrator-only.

### Task 2: Implement program-tree authorization predicates

**Files:**
- Modify: `backend/app/services/project_permission_service.py:1-150`
- Test: `backend/tests/test_project_permission_boundary_api.py`

**Step 1: Add the required model import and ownership helpers**

Import `Program`. Add `is_program_owner(db, program_id, user_id)`, which walks `Program.parent_id` from the target to the root and returns true if any active program in that chain has `owner_id == user_id`. Add `can_manage_program` and `ensure_program_manage_permission`, requiring authentication and allowing a system administrator or program-tree owner.

```python
def is_program_owner(db: Session, program_id: int | None, user_id: int | None) -> bool:
    while program_id and user_id is not None:
        program = db.query(Program).filter(Program.id == program_id, Program.deleted == 0).first()
        if not program:
            return False
        if program.owner_id == user_id:
            return True
        program_id = program.parent_id
    return False
```

**Step 2: Extend project management authorization**

In `can_manage_project`, load the active project and permit management when the actor owns its `program_id` through `is_program_owner`, in addition to the current system-admin and direct-project-owner checks. Keep direct project-owner behavior unchanged.

**Step 3: Add deletion predicates**

Change `can_delete_project` to accept `project_id`, then allow a system administrator or a direct/inherited manager only when no active project has `parent_id == project_id`. Add the analogous `can_delete_program`, allowing an owner only when no active child program has that `parent_id` and no active project has that `program_id`. Add `ensure_project_delete_permission(db, project_id, actor)` and `ensure_program_delete_permission(db, program_id, actor)` that return `403` when those predicates fail.

**Step 4: Run the focused tests**

Run: `pytest backend/tests/test_project_permission_boundary_api.py -v`

Expected: Tests still fail until the controllers are wired to the new predicates.

### Task 3: Apply unified authorization to project and program controllers

**Files:**
- Modify: `backend/app/controllers/project_controller.py:3-12,179-261`
- Modify: `backend/app/controllers/program_controller.py:1-21,51-116`
- Test: `backend/tests/test_project_permission_boundary_api.py`

**Step 1: Update project deletion authorization**

Pass `project_id` to `ensure_project_delete_permission` in `remove_project`. Do not alter its deletion service, so administrator cascade deletion remains intact.

**Step 2: Replace administrator-only program mutation dependencies**

Use `get_optional_current_user` and `ensure_program_manage_permission` for PATCH and all four lifecycle handlers. Pass the authenticated actor ID to lifecycle services for audit attribution. Use `ensure_program_delete_permission` in DELETE. Keep POST creation subject only to the authenticated-user rule described in `2026-07-22-authenticated-project-and-program-creation.md`.

**Step 3: Run the focused authorization test module**

Run: `pytest backend/tests/test_project_permission_boundary_api.py -v`

Expected: PASS; direct and inherited owners are allowed, unrelated users are rejected, owner deletion is leaf-only, and administrators retain global override.

**Step 4: Run affected API regression modules**

Run: `pytest backend/tests/test_project_permission_boundary_api.py backend/tests/test_program_project_api.py -v`

Expected: PASS with no failures.

**Step 5: Commit the backend permission change**

```bash
git add backend/app/services/project_permission_service.py backend/app/controllers/project_controller.py backend/app/controllers/program_controller.py backend/tests/test_project_permission_boundary_api.py
git commit -m "feat: unify project management permissions"
```

### Task 4: Align project and program UI actions with server authorization

**Files:**
- Modify: `frontend/src/utils/permissions.js`
- Modify: `frontend/src/views/ProjectsView.vue`
- Modify: `frontend/src/views/ProgramsView.vue`
- Modify: `frontend/src/utils/permissions.test.mjs`

**Step 1: Write failing permission-helper tests**

Add tests showing a direct owner can manage a project, a program owner can manage a project bound to a descendant program, and an unrelated user cannot. Add a pure helper for leaf detection using the already-loaded tree data, so owner delete controls are absent for non-leaf nodes.

**Step 2: Run the frontend helper tests to verify they fail**

Run: `npm test -- permissions`

Working directory: `frontend`

Expected: FAIL because the current helpers do not accept the program tree or apply inherited program ownership.

**Step 3: Implement the minimal UI predicates**

Extend the frontend permission helpers to evaluate the current program tree and whether a row is a leaf. Use those helpers to conditionally render edit, lifecycle, and delete actions in both list views. The UI only improves discoverability; the backend remains authoritative.

**Step 4: Run focused frontend tests**

Run: `npm test -- permissions`

Working directory: `frontend`

Expected: PASS.

**Step 5: Run frontend regression suite and build**

Run: `npm test`

Run: `npm run build`

Working directory: `frontend`

Expected: Both exit with status `0`.

**Step 6: Commit the UI alignment**

```bash
git add frontend/src/utils/permissions.js frontend/src/utils/permissions.test.mjs frontend/src/views/ProjectsView.vue frontend/src/views/ProgramsView.vue
git commit -m "feat: align management actions with ownership"
```
