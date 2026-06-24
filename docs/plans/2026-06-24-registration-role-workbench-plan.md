# Registration Role Workbench Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add self-service registration, role CRUD and user role assignment, and role-aware workbench defaults for DevOps/code review and active iteration work.

**Architecture:** Keep the first version as lightweight RBAC. Users register through `auth/register`, roles are managed through dedicated role APIs, and dashboard data is filtered/defaulted based on assigned role keys without introducing a full permission matrix.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, MySQL/SQLite tests, Vue 3, Pinia, Element Plus.

---

### Task 1: Registration API

**Files:**
- Modify: `backend/app/views/auth_view.py`
- Modify: `backend/app/services/user_service.py`
- Modify: `backend/app/controllers/auth_controller.py`
- Test: `backend/tests/test_user_api.py`

**Steps:**
1. Add failing tests for `POST /api/v1/auth/register`: success returns token, duplicate username returns 409, registered user can login.
2. Implement `RegisterRequest` with username, password, full_name, email, mobile, department.
3. Implement `register_user()` to hash password, enforce unique active username, default `is_active=True`.
4. Return the same token shape as login.
5. Run `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests/test_user_api.py -q`.
6. Commit: `feat: add user registration api`.

### Task 2: Role APIs And Assignment

**Files:**
- Create: `backend/app/views/role_view.py`
- Create: `backend/app/services/role_service.py`
- Create: `backend/app/controllers/role_controller.py`
- Modify: `backend/app/controllers/router.py`
- Modify: `backend/app/services/user_service.py`
- Modify: `backend/app/views/user_view.py`
- Test: `backend/tests/test_role_api.py`

**Steps:**
1. Add failing tests for listing seeded roles, creating a custom role, assigning roles to a user, and seeing role keys on user reads.
2. Seed default role keys: `system_admin`, `project_owner`, `product_manager`, `development_lead`, `developer`, `tester`, `viewer`.
3. Implement role CRUD: list, create, update, delete/disable.
4. Implement `PUT /api/v1/users/{user_id}/roles` with role id list.
5. Extend user read models to include `roles`.
6. Run role and user tests.
7. Commit: `feat: add role management api`.

### Task 3: Frontend Registration And Role Management

**Files:**
- Modify: `frontend/src/api/auth.js`
- Create: `frontend/src/api/roles.js`
- Modify: `frontend/src/api/users.js`
- Modify: `frontend/src/stores/auth.js`
- Modify: `frontend/src/views/LoginView.vue`
- Create: `frontend/src/views/RolesView.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/layout/MainLayout.vue`

**Steps:**
1. Add `register()` auth API and Pinia action.
2. Add a registration form to login page.
3. Add role management page for role CRUD and user-role assignment.
4. Add sidebar entry for role management.
5. Run `npm run build`.
6. Commit: `feat: add registration and role management UI`.

### Task 4: Code Review Role Assignment

**Files:**
- Modify: `backend/app/services/devops_service.py`
- Test: `backend/tests/test_devops_code_review_api.py`

**Steps:**
1. Add failing test: when a user has `development_lead`, new code review task owner is that user.
2. Implement development lead lookup through `roles` and `user_roles`.
3. Keep owner empty when no development lead exists.
4. Run DevOps tests.
5. Commit: `feat: assign code reviews to development leads`.

### Task 5: Role-Aware Workbench Defaults And Test Case Markers

**Files:**
- Modify: `backend/app/services/dashboard_service.py`
- Modify: `backend/app/controllers/dashboard_controller.py`
- Modify: `backend/app/views/dashboard_view.py`
- Modify: `frontend/src/views/DashboardView.vue`
- Test: `backend/tests/test_dashboard_workbench_api.py`

**Steps:**
1. Add tests for role-aware defaults: developer focuses on owned active iteration work; tester includes linked test cases; manager/lead sees broader active iteration work.
2. Add optional `username` or `user_id` dashboard query if needed, using current frontend user.
3. Add computed test case marker fields for linked completed/closed requirements/tasks/bugs, based on latest execution result.
4. Update dashboard UI to display role-aware defaults and test case markers.
5. Run dashboard tests and frontend build.
6. Commit: `feat: add role aware workbench defaults`.

### Task 6: Final Verification

**Steps:**
1. Run focused backend tests:
   `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests/test_user_api.py backend/tests/test_role_api.py backend/tests/test_devops_code_review_api.py backend/tests/test_dashboard_workbench_api.py -q`
2. Run frontend build: `npm run build` in `frontend`.
3. Run `git diff --check`.
4. Push all commits.
