# Handler Transition Rules Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add configurable current-handler transition rules so requirements, tasks, and bugs can move to the next processor when workflow status changes.

**Architecture:** Keep the existing creation-time assignee configuration in `assignee_rule_configs`. Add a separate `handler_transition_rules` table linked to that config, then call a small resolver from status-transition services after the status operation is recorded.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, Vue 3, Element Plus.

---

### Task 1: PRD Update

**Files:**
- Modify: `docs/prd/2026-07-01-current-handler-assignment-prd.md`

**Steps:**
1. Add a "处理人流转配置" section covering rule fields, default behavior, fallback behavior, and acceptance criteria.
2. Keep "创建时默认处理人" separate from "状态流转下一处理人".

### Task 2: Backend Red Tests

**Files:**
- Create: `backend/tests/test_handler_transition_rule_api.py`

**Steps:**
1. Add tests for transition-rule CRUD under an assignee rule config.
2. Add tests proving Bug `resolve` moves owner to tester and Bug `verify_failed` moves owner to developer.
3. Add tests proving Requirement `complete` moves owner to tester.
4. Add a no-rule fallback test proving owner stays unchanged.

### Task 3: Backend Implementation

**Files:**
- Create: `backend/app/models/handler_transition_rule.py`
- Create: `backend/app/views/handler_transition_rule_view.py`
- Create: `backend/app/services/handler_transition_rule_service.py`
- Create: `backend/app/controllers/handler_transition_rule_controller.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/controllers/router.py`
- Modify: `backend/app/db/schema.py`
- Modify: `backend/app/services/bug_service.py`
- Modify: `backend/app/services/requirement_service.py`
- Modify: `backend/app/services/task_service.py`

**Steps:**
1. Add model and schema table.
2. Add list/create/update/delete APIs.
3. Add resolver for next handler.
4. Apply resolver in status transitions and write an `auto_assign` status-operation entry when owner changes.

### Task 4: Frontend Configuration

**Files:**
- Create: `frontend/src/api/handlerTransitionRules.js`
- Modify: `frontend/src/views/WorkflowView.vue`

**Steps:**
1. Add API client methods.
2. Add a "处理人流转" configuration table.
3. Add create/edit/delete controls for object, action, statuses, target roles, fallback, and enabled.

### Task 5: Verification

**Commands:**
- `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_handler_transition_rule_api.py -q`
- `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_current_handler_assignment_api.py backend\tests\test_dashboard_workbench_api.py backend\tests\test_bug_workflow_api.py backend\tests\test_requirement_task_api.py -q`
- `npm run build` in `frontend`
