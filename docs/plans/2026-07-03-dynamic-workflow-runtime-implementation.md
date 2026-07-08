# Dynamic Workflow Runtime Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the dynamic workflow runtime so requirements, tasks, and bugs use workflow transitions for visible actions, execution, handler assignment, and history.

**Architecture:** Add runtime APIs that resolve the project workflow scheme, calculate available transitions from `workflow_transitions`, and execute transitions through domain handlers. Preserve existing fixed action endpoints during migration, but route new frontend actions through the runtime. Add `ui_config` and `form_config` JSON fields to transition storage.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, MySQL runtime schema patching, Vue 3, Element Plus.

---

### Task 1: Workflow Transition Config Fields

**Files:**
- Modify: `backend/app/models/workflow_definition.py`
- Modify: `backend/app/views/workflow_definition_view.py`
- Modify: `backend/app/db/schema.py`
- Test: `backend/tests/test_workflow_definition_api.py`

**Steps:**
1. Add failing test that saving a workflow graph persists `ui_config` and `form_config`.
2. Run the test and confirm it fails because fields are not accepted/returned.
3. Add JSON columns to model, view schemas, runtime schema creation, and runtime schema migration.
4. Run workflow definition tests.

### Task 2: Runtime API

**Files:**
- Create: `backend/app/views/workflow_runtime_view.py`
- Create: `backend/app/services/workflow_runtime_service.py`
- Create: `backend/app/controllers/workflow_runtime_controller.py`
- Modify: `backend/app/controllers/router.py`
- Test: `backend/tests/test_workflow_runtime_api.py`

**Steps:**
1. Add failing tests for available transitions, batch transitions, dynamic names, list primary/more placement, and transition execution.
2. Run tests and confirm failures.
3. Implement runtime transition lookup.
4. Implement transition execution with handler assignment, status history, and domain handlers for requirement/task/bug.
5. Add route registration.
6. Run runtime tests.

### Task 3: Frontend Runtime Client and Dynamic Action Component

**Files:**
- Create: `frontend/src/api/workflowRuntime.js`
- Create: `frontend/src/utils/workflowRuntimeActions.js`
- Create: `frontend/src/utils/workflowRuntimeActions.test.mjs`
- Create: `frontend/src/components/WorkflowActionButtons.vue`

**Steps:**
1. Add JS utility tests for primary/more button selection.
2. Run tests and confirm failure.
3. Implement API client and utility.
4. Implement compact dynamic action component using existing Element Plus patterns.
5. Run JS utility tests.

### Task 4: Wire Dynamic Actions into Pages

**Files:**
- Modify: `frontend/src/views/RequirementDetailView.vue`
- Modify: `frontend/src/views/TaskDetailView.vue`
- Modify: `frontend/src/views/BugDetailView.vue`
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/views/DashboardView.vue`

**Steps:**
1. Replace hard-coded state transition buttons with `WorkflowActionButtons`.
2. Keep edit/delete/create/import buttons outside workflow runtime.
3. Use batch runtime API for project/workbench list rows where practical.
4. Ensure dynamic forms submit payloads to runtime execution API.
5. Run frontend build.

### Task 5: Verification

**Files:**
- No direct code changes.

**Steps:**
1. Run backend workflow/runtime/current-handler tests.
2. Run frontend JS tests.
3. Run frontend production build.
4. Report changed files and any remaining migration caveats.
