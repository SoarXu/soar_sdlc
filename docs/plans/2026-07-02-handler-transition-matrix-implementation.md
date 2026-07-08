# Handler Transition Matrix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the confirmed handler transition matrix PRD, including matrix rules, last-resolver routing, and unassigned work item management.

**Architecture:** Keep `handler_transition_rules` as the single storage table. Add a matrix API facade for simple status-to-handler configuration, keep advanced rules on the existing API, and centralize cross-object work item operations in a new service/controller.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, Vue 3, Element Plus, Vite.

---

### Task 1: Matrix Rule API

**Files:**
- Modify: `backend/app/models/handler_transition_rule.py`
- Modify: `backend/app/views/handler_transition_rule_view.py`
- Modify: `backend/app/services/handler_transition_rule_service.py`
- Modify: `backend/app/controllers/handler_transition_rule_controller.py`
- Modify: `backend/app/controllers/router.py`
- Modify: `backend/app/db/schema.py`
- Test: `backend/tests/test_handler_transition_matrix_api.py`

**Steps:**
1. Write failing tests for matrix batch save, read, default template, and advanced-rule override.
2. Run `E:\miniforge3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_handler_transition_matrix_api.py -q` and confirm failures.
3. Add `rule_type` and `fallback_roles` fields.
4. Add `GET/PUT/POST apply-template` matrix endpoints.
5. Update rule matching to prefer enabled advanced rules, then enabled matrix rules.
6. Re-run the focused tests until green.

### Task 2: Last Resolver And Fallback Roles

**Files:**
- Modify: `backend/app/services/handler_transition_rule_service.py`
- Test: `backend/tests/test_handler_transition_matrix_api.py`

**Steps:**
1. Write failing test proving Bug verify failed routes to the latest resolver.
2. Implement `target_type=last_resolver` using `bugs.resolved_by`, then `status_operation_log action=resolve`.
3. Implement `fallback_roles` for project-role fallback resolution.
4. Re-run focused tests.

### Task 3: Unified Work Items

**Files:**
- Create: `backend/app/views/work_item_view.py`
- Create: `backend/app/services/work_item_service.py`
- Create: `backend/app/controllers/work_item_controller.py`
- Modify: `backend/app/controllers/router.py`
- Test: `backend/tests/test_unassigned_work_items_api.py`

**Steps:**
1. Write failing tests for unassigned list, claim, assign, batch assign, and auto assign.
2. Implement cross-object query and mutations for requirement/task/bug.
3. Reuse existing assignment permission and project-member checks.
4. Add waiting duration and overdue flags.
5. Re-run focused tests.

### Task 4: Frontend Matrix And Workbench Wiring

**Files:**
- Create: `frontend/src/api/handlerTransitionMatrix.js`
- Create: `frontend/src/api/workItems.js`
- Modify: `frontend/src/views/WorkflowView.vue`
- Modify: `frontend/src/views/DashboardView.vue`

**Steps:**
1. Add matrix API client and work item API client.
2. Replace the default transition configuration panel with object tabs for requirement/task/bug matrix rows.
3. Keep advanced rules collapsed.
4. Add workbench views for my todo, unassigned, unplanned, team todo, and all items.
5. Add claim, assign, batch assign, auto assign controls for unassigned items.

### Task 5: Verification And Run

**Commands:**
- `E:\miniforge3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_handler_transition_matrix_api.py backend\tests\test_unassigned_work_items_api.py -q`
- `E:\miniforge3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_handler_transition_rule_api.py backend\tests\test_current_handler_assignment_api.py backend\tests\test_dashboard_workbench_api.py backend\tests\test_bug_workflow_api.py backend\tests\test_requirement_task_api.py -q`
- `node frontend\src\utils\workItemStatusOptions.test.mjs`
- `npm run build`

**Run services:**
- Backend from `backend`: `E:\miniforge3\envs\soar_sdlc_py311\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- Frontend from `frontend`: `npm run dev -- --host 0.0.0.0`
