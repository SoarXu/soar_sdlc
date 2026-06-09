# Intellective Bio SDLC MVP Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the PRD-defined智享生物 SDLC 项目管理平台 MVP with FastAPI MVC backend and Vue3 frontend.

**Architecture:** The backend keeps MVC boundaries: `models/` for SQLAlchemy entities, `views/` for request/response DTOs, `controllers/` for HTTP routes, and `services/` for business rules. The frontend uses Vue3 + Element Plus with one desktop shell, side navigation, dynamic list/form rendering, and module-specific pages. Configuration-heavy features such as form fields and workflow rules are stored in database tables and surfaced through APIs.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, Pydantic, JWT, Vue3, Vite, Pinia, Axios, Element Plus, SQLite for local development.

**Constraints:** The current workspace is not a Git repository, so commit steps are not executable. The current machine has Node/npm but no Python launcher, so backend tests and API boot verification require installing Python 3.11+ first.

---

## Phase 1: Backend Domain Foundation

### Task 1: Add Backend Test Harness

**Files:**
- Create: `backend/pytest.ini`
- Create: `backend/requirements-dev.txt`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

**Steps:**
1. Add `pytest`, `httpx`, and `pytest-cov` to `backend/requirements-dev.txt`.
2. Configure `pytest.ini` with `pythonpath = .`.
3. Create a FastAPI `TestClient` fixture that imports `app.main.app`.
4. Write a test for `GET /api/v1/health`.
5. Run `pytest backend/tests/test_health.py -v`.
6. Expected after Python install: health test passes.

### Task 2: Replace Demo Project Model With PRD Core Models

**Files:**
- Modify: `backend/app/models/project.py`
- Create: `backend/app/models/program.py`
- Create: `backend/app/models/iteration.py`
- Create: `backend/app/models/requirement.py`
- Create: `backend/app/models/task.py`
- Create: `backend/app/models/test_case.py`
- Create: `backend/app/models/test_run.py`
- Create: `backend/app/models/bug.py`
- Create: `backend/app/models/field_registry.py`
- Create: `backend/app/models/workflow_rule.py`
- Create: `backend/app/models/relation.py`
- Create: `backend/app/models/notification.py`
- Create: `backend/app/models/audit_log.py`
- Create: `backend/app/models/integration_mapping.py`
- Modify: `backend/app/models/__init__.py`

**Steps:**
1. Write failing model metadata tests checking all required tables exist.
2. Implement models with integer autoincrement `id` as primary key.
3. Keep display codes out of primary keys; use helper formatting later.
4. Add foreign keys where stable and use `object_relation` for generic relations.
5. Include timestamp columns consistently.
6. Run model tests.

### Task 3: Add Pydantic Views for All PRD Objects

**Files:**
- Create: `backend/app/views/common.py`
- Create: `backend/app/views/program_view.py`
- Modify: `backend/app/views/project_view.py`
- Create: `backend/app/views/iteration_view.py`
- Create: `backend/app/views/requirement_view.py`
- Create: `backend/app/views/task_view.py`
- Create: `backend/app/views/test_case_view.py`
- Create: `backend/app/views/test_run_view.py`
- Create: `backend/app/views/bug_view.py`
- Create: `backend/app/views/field_registry_view.py`
- Create: `backend/app/views/workflow_view.py`
- Create: `backend/app/views/notification_view.py`
- Create: `backend/app/views/audit_view.py`

**Steps:**
1. Write tests validating request payloads for required fields.
2. Add `Create`, `Update`, `Read`, and list query view classes.
3. Include dynamic field payload support via `custom_fields`.
4. Run view validation tests.

### Task 4: Implement Generic CRUD and Audit Services

**Files:**
- Create: `backend/app/services/crud_service.py`
- Create: `backend/app/services/audit_service.py`
- Modify: existing services under `backend/app/services/`

**Steps:**
1. Write tests for create/update/delete audit log generation.
2. Implement generic CRUD helpers for list, get, create, update, soft delete.
3. Implement `audit_log` creation with before/after JSON.
4. Ensure delete is soft delete where PRD requires historical retention.
5. Run service tests.

## Phase 2: Field Registry and Dynamic Forms

### Task 5: Implement Field Registry APIs

**Files:**
- Create: `backend/app/controllers/field_registry_controller.py`
- Modify: `backend/app/controllers/router.py`
- Create: `backend/app/services/field_registry_service.py`
- Add tests under: `backend/tests/test_field_registry.py`

**Steps:**
1. Write failing tests for listing fields by object type.
2. Write failing tests preventing disabling required system fields.
3. Implement field registry list/create/update APIs.
4. Seed PRD-defined system fields for all core object types.
5. Run field registry tests.

### Task 6: Implement Custom Field Values

**Files:**
- Modify: `backend/app/models/field_registry.py`
- Create: `backend/app/services/custom_field_service.py`
- Add tests under: `backend/tests/test_custom_fields.py`

**Steps:**
1. Write tests for saving `text`, `number`, `date`, and `json` custom values.
2. Implement custom value persistence.
3. Attach custom fields to create/update/read flows.
4. Run custom field tests.

### Task 7: Build Frontend Dynamic Field Registry Screen

**Files:**
- Create: `frontend/src/api/fieldRegistry.js`
- Create: `frontend/src/views/FieldRegistryView.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/layout/MainLayout.vue`

**Steps:**
1. Add route and sidebar item for 字段注册中心.
2. Build object type selector.
3. Show fields with toggles: 表单展示、列表展示、必填、搜索、启用.
4. Add custom field dialog.
5. Run `npm run build`.

## Phase 3: Core Object APIs

### Task 8: Program and Project APIs

**Files:**
- Create: `backend/app/controllers/program_controller.py`
- Modify: `backend/app/controllers/project_controller.py`
- Create: `backend/app/services/program_service.py`
- Modify: `backend/app/services/project_service.py`
- Tests: `backend/tests/test_program_project.py`

**Steps:**
1. Write tests for program CRUD and project CRUD.
2. Write tests for project owner change sync options.
3. Implement endpoints and services.
4. Log owner sync operations.
5. Run tests.

### Task 9: Iteration, Requirement, and Task APIs

**Files:**
- Create controllers/services/views as needed for iteration, requirement, task.
- Tests: `backend/tests/test_requirement_task_flow.py`

**Steps:**
1. Write failing test: requirement can generate task without review by default.
2. Write failing test: project workflow can require reviewed requirement before task generation.
3. Write failing test: requirement cannot complete when child tasks remain unfinished.
4. Implement requirement CRUD, task CRUD, generate-task action, and status transition action.
5. Run tests.

### Task 10: Test Case, Test Run, and Bug APIs

**Files:**
- Create controllers/services/views as needed for test case, test run, bug.
- Tests: `backend/tests/test_testing_bug_flow.py`

**Steps:**
1. Write tests for test case tags and requirement association.
2. Write tests for creating test run from selected cases.
3. Write tests for creating Bug from failed test result with owner inherited from requirement.
4. Write tests for Bug status flow: 待修复 -> 修复中 -> 待验证 -> 已关闭.
5. Implement services and endpoints.
6. Run tests.

## Phase 4: Workflow, Relations, Notifications

### Task 11: Workflow Rule Templates

**Files:**
- Create: `backend/app/controllers/workflow_controller.py`
- Create: `backend/app/services/workflow_service.py`
- Tests: `backend/tests/test_workflow_rules.py`

**Steps:**
1. Write tests for default rule values from PRD.
2. Write tests for project-level override.
3. Implement rule template storage and rule evaluation helpers.
4. Wire rule checks into owner sync, task generation, requirement completion, iteration finish, and Bug closure.
5. Run workflow tests.

### Task 12: Object Relations

**Files:**
- Create: `backend/app/controllers/relation_controller.py`
- Create: `backend/app/services/relation_service.py`
- Tests: `backend/tests/test_object_relations.py`

**Steps:**
1. Write tests for requirement -> task generated relation.
2. Write tests for requirement -> case coverage relation.
3. Write tests for test run -> case execution relation.
4. Implement generic relation APIs and automatic relation creation.
5. Run tests.

### Task 13: Notifications and DingTalk Reservation

**Files:**
- Create: `backend/app/controllers/notification_controller.py`
- Create: `backend/app/services/notification_service.py`
- Tests: `backend/tests/test_notifications.py`

**Steps:**
1. Write tests for in-app notification creation on assignment and Bug status change.
2. Write tests for DingTalk channel config storage.
3. Write tests for delivery log creation without actual sending.
4. Implement notification tables and APIs.
5. Run tests.

### Task 14: External Integration Mapping

**Files:**
- Create: `backend/app/controllers/integration_controller.py`
- Create: `backend/app/services/integration_service.py`
- Tests: `backend/tests/test_integration_mapping.py`

**Steps:**
1. Write tests for mapping local object ID to GitLab issue IID.
2. Implement mapping CRUD APIs.
3. Keep actual GitLab synchronization out of MVP.
4. Run tests.

## Phase 5: Frontend Application

### Task 15: Shared Frontend Data Layer

**Files:**
- Create API modules for each backend resource under `frontend/src/api/`.
- Create Pinia stores under `frontend/src/stores/`.
- Create reusable components:
  - `frontend/src/components/DynamicForm.vue`
  - `frontend/src/components/ConfigurableTable.vue`
  - `frontend/src/components/ObjectRelationPanel.vue`
  - `frontend/src/components/StatusTag.vue`

**Steps:**
1. Build typed API wrappers in plain JS.
2. Build dynamic form from field registry metadata.
3. Build configurable table from `is_list_visible` fields.
4. Run `npm run build`.

### Task 16: Core Module Pages

**Files:**
- Create Vue views for:
  - `ProgramsView.vue`
  - `ProjectsView.vue`
  - `IterationsView.vue`
  - `RequirementsView.vue`
  - `TasksView.vue`
  - `TestCasesView.vue`
  - `TestRunsView.vue`
  - `BugsView.vue`
  - `WorkflowView.vue`
  - `NotificationsView.vue`
  - `AuditLogView.vue`
  - `DevOpsView.vue`
- Modify router and sidebar.

**Steps:**
1. Build CRUD list pages using shared components.
2. Add owner sync modal in project page.
3. Add generate task action in requirement page.
4. Add status transition controls with backend validation.
5. Add relation panel in requirement and Bug details.
6. Run `npm run build`.

### Task 17: Dashboard and Global Search

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`
- Create: `backend/app/controllers/search_controller.py`
- Create: `backend/app/services/search_service.py`

**Steps:**
1. Implement dashboard summary API.
2. Implement keyword search across ID/title/name.
3. Connect top search input to global search result page.
4. Run frontend build.

## Phase 6: Documentation and Verification

### Task 18: README and API Documentation

**Files:**
- Modify: `README.md`
- Create: `docs/api/README.md`

**Steps:**
1. Document all modules and startup commands.
2. Document Python dependency requirement.
3. Document MVP limitations: DevOps placeholder, DingTalk reserved, GitLab mapping only.

### Task 19: End-to-End Manual Verification

**Steps:**
1. Start backend: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
2. Start frontend: `npm run dev -- --host 127.0.0.1`.
3. Verify login.
4. Create project set, project, requirement, task, test case, test run, Bug.
5. Verify owner sync, task generation, requirement completion block, iteration Finish block, Bug closure rule, field registry dynamic display.
6. Verify `npm run build`.

## Execution Order

Implement phases strictly in order:

1. Backend tests and domain foundation.
2. Field registry and custom fields.
3. Core object APIs.
4. Workflow, relations, notifications.
5. Frontend shared components.
6. Frontend module pages.
7. Documentation and full verification.

Do not implement later UI pages before backend contracts exist. Do not add production behavior without tests first.
