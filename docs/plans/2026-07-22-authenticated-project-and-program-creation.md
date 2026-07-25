# Authenticated Project and Program Creation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Allow every authenticated user, regardless of role, to create a project or project group while anonymous requests remain unauthorized.

**Architecture:** The two POST controllers resolve the current user through the existing authentication dependency and no longer require the `system_admin` role. The project-list Vue view renders creation controls unconditionally; all existing update, lifecycle, membership, and deletion authorization remains untouched.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3, Node.js built-in test runner.

---

### Task 1: Add backend authorization regression coverage

**Files:**
- Modify: `backend/tests/test_program_project_api.py`

**Step 1: Write the failing test**

Add a test that creates an active `User` with no role assignment, generates a token with `create_access_token`, and sends authenticated creation requests:

```python
def test_authenticated_non_admin_can_create_projects_and_programs(client: TestClient):
    db = SessionLocal()
    try:
        user = User(
            username=f"project.creator.{uuid4().hex[:6]}",
            full_name="Project Creator",
            password_hash=get_password_hash("User123456"),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        headers = {"Authorization": f"Bearer {create_access_token(user.username)}"}
    finally:
        db.close()

    assert client.post("/api/v1/programs", json={"name": f"Program {uuid4().hex[:8]}"}, headers=headers).status_code == 200
    assert client.post("/api/v1/projects", json={"name": f"Project {uuid4().hex[:8]}"}, headers=headers).status_code == 200
    assert client.post("/api/v1/programs", json={"name": "Anonymous program"}, headers={"X-Test-No-Auth": "1"}).status_code == 401
    assert client.post("/api/v1/projects", json={"name": "Anonymous project"}, headers={"X-Test-No-Auth": "1"}).status_code == 401
```

**Step 2: Run the test to verify it fails**

Run: `pytest backend/tests/test_program_project_api.py::test_authenticated_non_admin_can_create_projects_and_programs -v`

Expected: FAIL because the authenticated non-admin receives `403` from the system-administrator dependency.

**Step 3: Implement the minimal controller change**

Defer implementation to Task 2. Do not change authorization for non-creation endpoints.

**Step 4: Run the test again**

Run: `pytest backend/tests/test_program_project_api.py::test_authenticated_non_admin_can_create_projects_and_programs -v`

Expected: It remains failing until Task 2 is complete.

### Task 2: Require authentication, not administrator role, on creation endpoints

**Files:**
- Modify: `backend/app/controllers/project_controller.py:170-176`
- Modify: `backend/app/controllers/program_controller.py:36-42`
- Test: `backend/tests/test_program_project_api.py`

**Step 1: Make the minimal implementation change**

Replace the unused administrator dependency parameter on both POST handlers with the existing authenticated-user dependency:

```python
current_user: User = Depends(get_current_user),
```

Import `get_current_user` from `app.core.auth_dependencies`. Keep the variable intentionally unused because it establishes the authentication boundary. Do not modify PATCH, DELETE, member-management, or lifecycle endpoints.

**Step 2: Run the focused backend test**

Run: `pytest backend/tests/test_program_project_api.py::test_authenticated_non_admin_can_create_projects_and_programs -v`

Expected: PASS; the non-admin token creates both resources and requests with `X-Test-No-Auth` return `401`.

**Step 3: Run the complete affected API test module**

Run: `pytest backend/tests/test_program_project_api.py -v`

Expected: PASS with no failures.

**Step 4: Commit the backend change**

```bash
git add backend/app/controllers/project_controller.py backend/app/controllers/program_controller.py backend/tests/test_program_project_api.py
git commit -m "feat: allow authenticated project creation"
```

### Task 3: Expose project creation controls to every signed-in user

**Files:**
- Create: `frontend/src/views/projectCreationPermission.test.mjs`
- Modify: `frontend/src/views/ProjectsView.vue:8,60,178-200`

**Step 1: Write the failing frontend test**

Create a source-level regression test that reads `ProjectsView.vue` and asserts both `新增项目` controls do not contain `v-if="canCreateProject"`, while the delete control still references `canDeleteProjectRow`.

```javascript
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./ProjectsView.vue', import.meta.url), 'utf8')

assert.doesNotMatch(source, /v-if="canCreateProject"/)
assert.match(source, /v-if="canDeleteProjectRow"/)
```

**Step 2: Run the test to verify it fails**

Run: `npm test -- projectCreationPermission`

Working directory: `frontend`

Expected: FAIL because both project-create buttons currently use `v-if="canCreateProject"`.

**Step 3: Implement the minimal view change**

Remove the `v-if="canCreateProject"` attributes from the root and child-project creation buttons. Remove the now-unused `isSystemAdmin` import and `canCreateProject` computed value. Retain `currentUser` because delete and project-management controls still use it.

**Step 4: Run the focused frontend test**

Run: `npm test -- projectCreationPermission`

Working directory: `frontend`

Expected: PASS.

**Step 5: Run the full frontend suite and production build**

Run: `npm test`

Run: `npm run build`

Working directory: `frontend`

Expected: Both commands exit with status `0`.

**Step 6: Commit the frontend change**

```bash
git add frontend/src/views/ProjectsView.vue frontend/src/views/projectCreationPermission.test.mjs
git commit -m "feat: show project creation to authenticated users"
```
