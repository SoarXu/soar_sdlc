# System Admin User And Role Management Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add system-admin-only role and user administration with secure one-time initial passwords and forced first-login password changes.

**Architecture:** Backend enforces all permissions through authenticated dependencies and role checks. User password lifecycle is tracked with a `must_change_password` column, secure random password generation, and a change-password endpoint. Frontend adds admin-only controls in role management and routes forced-password-change users to a dedicated screen.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, PyTest, Vue 3, Pinia, Vue Router, Element Plus.

---

### Task 1: Backend Tests For Admin Authorization And Password Lifecycle

**Files:**
- Modify: `backend/tests/test_user_api.py`
- Modify: `backend/tests/test_role_api.py`

**Step 1: Write failing tests**

- Add tests that a non-admin authenticated user receives `403` for `POST /api/v1/roles`.
- Add tests that an admin can create a user through `POST /api/v1/users` and receives `initial_password`.
- Add tests that the created user login response includes `must_change_password=true`.
- Add tests that `POST /api/v1/auth/change-password` clears the flag.
- Add tests that `POST /api/v1/users/{id}/reset-password` returns a new `initial_password` and sets the flag again.

**Step 2: Run tests to verify failure**

Run:

```bash
cd backend
pytest tests/test_user_api.py tests/test_role_api.py -q
```

Expected: FAIL because endpoints, fields, and authorization dependency do not exist yet.

### Task 2: Backend Schema And Auth Dependency

**Files:**
- Modify: `backend/app/models/user.py`
- Modify: `backend/app/db/schema.py`
- Modify: `backend/app/core/auth_dependencies.py`
- Modify: `backend/app/views/auth_view.py`
- Modify: `backend/app/views/user_view.py`

**Step 1: Implement minimal schema fields**

- Add `must_change_password` to `User`.
- Add runtime schema migration for existing databases.
- Add response fields for login and user reads.

**Step 2: Implement admin dependency**

- Add `get_current_user`.
- Add `require_system_admin`.
- Query `UserRole` joined to `Role` for enabled `system_admin`.
- Return `401` for missing/invalid token and `403` for non-admin.

**Step 3: Run backend tests**

Run:

```bash
cd backend
pytest tests/test_user_api.py tests/test_role_api.py -q
```

Expected: Still FAIL only for missing service endpoints and password flow.

### Task 3: Backend User Password Lifecycle APIs

**Files:**
- Modify: `backend/app/services/user_service.py`
- Modify: `backend/app/controllers/auth_controller.py`
- Modify: `backend/app/controllers/user_controller.py`
- Modify: `backend/app/views/auth_view.py`
- Modify: `backend/app/views/user_view.py`
- Modify: `backend/app/api router` if required by current route wiring

**Step 1: Implement secure password generation**

- Use `secrets.SystemRandom`.
- Generate 16-character passwords with at least one lowercase, uppercase, digit, and symbol.
- Store only password hashes.

**Step 2: Implement APIs**

- `POST /api/v1/users` creates admin-managed users, assigns selected roles, returns `initial_password`.
- `POST /api/v1/users/{id}/reset-password` resets password and returns one-time `initial_password`.
- `POST /api/v1/auth/change-password` verifies old password, validates new password length, updates hash, clears `must_change_password`.
- Login response includes `must_change_password`.

**Step 3: Run backend tests**

Run:

```bash
cd backend
pytest tests/test_user_api.py tests/test_role_api.py -q
```

Expected: PASS.

### Task 4: Protect Role And User Mutation APIs

**Files:**
- Modify: `backend/app/controllers/role_controller.py`
- Modify: `backend/app/controllers/user_controller.py`

**Step 1: Apply `require_system_admin`**

- Add dependency to role create/update/delete.
- Add dependency to user create, role assignment, and reset password.

**Step 2: Run targeted tests**

Run:

```bash
cd backend
pytest tests/test_user_api.py tests/test_role_api.py -q
```

Expected: PASS.

### Task 5: Frontend Session And Forced Password Change

**Files:**
- Modify: `frontend/src/api/auth.js`
- Modify: `frontend/src/stores/auth.js`
- Modify: `frontend/src/router/index.js`
- Create: `frontend/src/views/ChangePasswordView.vue`

**Step 1: Add API and store state**

- Add `changePassword(payload)` API.
- Store `must_change_password` in localStorage/session state.

**Step 2: Add route guard**

- If logged in and `must_change_password=true`, route to `/change-password`.
- After successful password change, clear flag and route to original destination or `/`.

**Step 3: Build frontend**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

### Task 6: Frontend Role Management User Administration

**Files:**
- Modify: `frontend/src/api/users.js`
- Modify: `frontend/src/views/RolesView.vue`

**Step 1: Add user APIs**

- `createUser(data)`
- `resetUserPassword(userId)`

**Step 2: Add UI controls**

- Add `新增用户` button.
- Add create-user dialog with account profile and role selection.
- Add reset password button per user.
- Add one-time password dialog with copy button.
- Hide/disable mutation controls when current user does not have `system_admin`.

**Step 3: Build frontend**

Run:

```bash
cd frontend
npm run build
```

Expected: PASS.

### Task 7: Final Verification

**Files:**
- No code changes expected.

**Step 1: Run backend targeted tests**

```bash
cd backend
pytest tests/test_user_api.py tests/test_role_api.py -q
```

**Step 2: Run frontend build**

```bash
cd frontend
npm run build
```

**Step 3: Smoke test running app**

- Login as `admin/admin123`.
- Create a user in role management.
- Copy initial password.
- Login as the new user.
- Verify forced password change.
- Login again with the new password.
