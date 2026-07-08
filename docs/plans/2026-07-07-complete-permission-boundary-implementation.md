# Complete Permission Boundary Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete the PRD-defined backend permission boundary for all write operations and audit/history reads.

**Architecture:** Reuse the existing `project_permission_service.py` as the central permission module. Controllers resolve the current user and project scope, then call permission helpers before delegating to existing services. Services keep business validation and persistence logic.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue/Vite.

---

### Task 1: Red Tests

**Files:**
- Modify: `backend/tests/test_project_permission_boundary_api.py`

**Steps:**
1. Add tests for login-required work item creation.
2. Add tests for work item delete permission.
3. Add tests for project lifecycle permissions.
4. Add tests for test case manage/execute permissions.
5. Add tests for workflow configuration permissions.

### Task 2: Permission Service

**Files:**
- Modify: `backend/app/services/project_permission_service.py`

**Steps:**
1. Add login-required helper.
2. Add work item create/delete helpers.
3. Add test case manage/execute helpers.
4. Add workflow configuration helper.
5. Keep unauthenticated compatibility only for explicitly public read operations.

### Task 3: Project And Work Item Controllers

**Files:**
- Modify: `backend/app/controllers/project_controller.py`
- Modify: `backend/app/controllers/requirement_controller.py`
- Modify: `backend/app/controllers/task_controller.py`
- Modify: `backend/app/controllers/bug_controller.py`

**Steps:**
1. Require project management permission for project lifecycle operations.
2. Require create permission for requirement/task/bug creation and requirement import.
3. Require delete permission for requirement/task/bug deletion.
4. Require current-handler/admin permission for generating task from requirement.

### Task 4: Test Controllers

**Files:**
- Modify: `backend/app/controllers/test_case_controller.py`
- Modify: `backend/app/controllers/test_run_controller.py`

**Steps:**
1. Require test case manage permission for create/edit/delete.
2. Require test execute permission for execution records and submit-bug actions.
3. Require test case manage permission for test run planning operations.

### Task 5: Workflow Configuration Controllers

**Files:**
- Modify: `backend/app/controllers/assignee_rule_config_controller.py`
- Modify: `backend/app/controllers/workflow_definition_controller.py`
- Modify: `backend/app/controllers/handler_transition_rule_controller.py`
- Modify: `backend/app/controllers/workflow_controller.py`

**Steps:**
1. Require system admin for global workflow scheme create/update/delete.
2. Preserve read endpoints.
3. Keep deprecated workflow rule writes protected.

### Task 6: Verification

**Commands:**
- `E:\miniforge3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_project_permission_boundary_api.py -q`
- `E:\miniforge3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_iteration_detail_api.py backend\tests\test_requirement_task_api.py backend\tests\test_test_case_execution_api.py backend\tests\test_workflow_definition_api.py -q`
- `npm run build`
