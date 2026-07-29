# Workbench Terminal Tabs Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add completed and terminated workbench tabs for terminal requirements, tasks, and bugs in active iterations.

**Architecture:** Persist an explicit terminal outcome on workflow states and expose it through the workflow graph API. The dashboard service classifies active-iteration work items by that outcome; the Vue workbench consumes two new API sections using its established tab and table patterns.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, Vue 3, Element Plus, Node assertion tests, pytest.

---

### Task 1: Persist and validate terminal outcomes

**Files:**
- Modify: `backend/app/models/workflow_definition.py`
- Modify: `backend/app/views/workflow_definition_view.py`
- Modify: `backend/app/services/workflow_definition_service.py`
- Modify: `backend/app/services/default_workflow_template_service.py`
- Create: `backend/alembic/versions/20260729_001_workflow_state_terminal_kind.py`
- Test: `backend/tests/test_workflow_definition_api.py`

**Step 1: Write the failing test**

Add graph-save assertions that terminal states accept `terminal_kind` values `completed` and `terminated`, reject either value on non-terminal states and reject unknown values. Assert default requirement, task, and bug templates identify their normal completion states as `completed` and cancellation/rejection states as `terminated` where present.

**Step 2: Run the focused test**

Run: `pytest backend/tests/test_workflow_definition_api.py -q`
Expected: FAIL because the graph schema does not accept or validate `terminal_kind`.

**Step 3: Write minimal implementation**

Add nullable `terminal_kind` to `WorkflowState`, expose it through state read/save/template schemas, validate it only on terminal states, and declare the values on default-template terminal states. Add an Alembic migration that creates the nullable column without guessing values for existing workflow states.

**Step 4: Run the focused test**

Run: `pytest backend/tests/test_workflow_definition_api.py -q`
Expected: PASS.

**Step 5: Commit**

Commit the model, API schema, validator, template, migration, and focused test with `feat: classify terminal workflow states`.

### Task 2: Configure terminal outcome in the workflow designer

**Files:**
- Modify: `frontend/src/components/WorkflowAdvancedConfigDrawer.vue`
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Test: `frontend/src/components/workflowAdvancedConfigDrawer.test.mjs`

**Step 1: Write the failing test**

Assert that state configuration renders a terminal-outcome select only for terminal states and that the graph payload retains `terminal_kind`.

**Step 2: Run the focused test**

Run: `node frontend/src/components/workflowAdvancedConfigDrawer.test.mjs`
Expected: FAIL because no terminal-outcome control exists.

**Step 3: Write minimal implementation**

Add a conditional Element Plus select with `已完成` and `已终止` options. Clear `terminal_kind` when a state changes away from `terminal`; retain it in all graph cloning and save paths.

**Step 4: Run the focused test**

Run: `node frontend/src/components/workflowAdvancedConfigDrawer.test.mjs`
Expected: PASS.

**Step 5: Commit**

Commit the component, state-copy path, and test with `feat: configure terminal workflow outcomes`.

### Task 3: Return terminal outcome sections from the workbench API

**Files:**
- Modify: `backend/app/views/dashboard_view.py`
- Modify: `backend/app/services/dashboard_service.py`
- Test: `backend/tests/test_dashboard_workbench_api.py`

**Step 1: Write the failing test**

Create active-iteration requirements, tasks, and bugs in terminal states classified as completed and terminated. Assert they appear only in their matching response sections, that a terminal state without an outcome appears in neither, and that completed-iteration or unauthorized-project items remain excluded.

**Step 2: Run the focused test**

Run: `pytest backend/tests/test_dashboard_workbench_api.py -q`
Expected: FAIL because the response lacks `completed` and `terminated` sections.

**Step 3: Write minimal implementation**

Expose `terminal_kind` on workbench items, compose all active-scoped work items once, and partition terminal items into `completed` and `terminated` sections. Keep current non-terminal queue behavior unchanged.

**Step 4: Run the focused test**

Run: `pytest backend/tests/test_dashboard_workbench_api.py -q`
Expected: PASS.

**Step 5: Commit**

Commit the dashboard response, service, and test with `feat: expose terminal workbench sections`.

### Task 4: Render terminal sections in the workbench

**Files:**
- Modify: `frontend/src/utils/workbenchViewModel.js`
- Modify: `frontend/src/views/DashboardView.vue`
- Test: `frontend/src/utils/workbenchViewModel.test.mjs`

**Step 1: Write the failing test**

Provide completed and terminated payload sections and assert they become first-level entry tabs, queue sections, keyed sections, and summary cards with their expected totals. Assert the dashboard source integrates the two tab keys.

**Step 2: Run the focused test**

Run: `node frontend/src/utils/workbenchViewModel.test.mjs`
Expected: FAIL because the view model ignores the sections.

**Step 3: Write minimal implementation**

Add `已完成` and `已终止` tabs after the existing operational queues, normalize their payload sections, include them in table selection and transition-loading inputs, and show a success tag for completed rows and a neutral/danger tag for terminated rows.

**Step 4: Run the focused test and build**

Run: `node frontend/src/utils/workbenchViewModel.test.mjs` and `npm --prefix frontend run build`
Expected: PASS and a successful Vite build.

**Step 5: Commit**

Commit the view model, workbench view, and test with `feat: display terminal workbench tabs`.

### Task 5: Verify the integrated change

**Files:**
- Verify: `backend/tests/test_workflow_definition_api.py`
- Verify: `backend/tests/test_dashboard_workbench_api.py`
- Verify: `frontend/src/utils/workbenchViewModel.test.mjs`
- Verify: `frontend/src/components/workflowAdvancedConfigDrawer.test.mjs`

**Step 1: Run targeted backend tests**

Run: `pytest backend/tests/test_workflow_definition_api.py backend/tests/test_dashboard_workbench_api.py -q`
Expected: PASS.

**Step 2: Run frontend tests and build**

Run: `npm --prefix frontend test` and `npm --prefix frontend run build`
Expected: PASS and a successful build.

**Step 3: Inspect the final diff**

Run: `git diff --check` and `git status --short`
Expected: no whitespace errors and only intended feature files beyond the pre-existing user changes.
