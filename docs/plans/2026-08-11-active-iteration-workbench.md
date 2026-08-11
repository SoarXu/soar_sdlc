# 进行中迭代单表工作台 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Show all visible requirements, tasks, and Bugs in in-progress iterations in one filterable workbench table with deterministic operational sorting.

**Architecture:** Add a canonical active-iteration work-item collection to the existing dashboard response after applying project-visibility rules. Replace queue-driven dashboard selection with this collection, filtering and sorting it in the frontend while reusing existing detail, workflow and batch-assignment actions.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, Vue 3, Element Plus, Node built-in assertions, Vite.

---

### Task 1: Add a failing backend contract for the canonical workbench list

**Files:**
- Modify: `backend/tests/test_dashboard_workbench_api.py`
- Modify: `backend/app/views/dashboard_view.py`

**Step 1: Write the failing API test**

Create visible and invisible projects with in-progress iterations, then create requirements, tasks and Bugs in each. Include terminal work items in the visible iteration. Assert that `GET /api/v1/dashboard/workbench` returns a canonical `active_iteration_items` collection containing every visible in-progress-iteration item exactly once, including completed/cancelled items, and no item from an invisible project or non-in-progress iteration.

**Step 2: Run the focused test to verify it fails**

Run: `pytest tests/test_dashboard_workbench_api.py -q`

Expected: FAIL because the response currently contains only source-specific queue sections.

### Task 2: Build the permission-scoped active-iteration collection

**Files:**
- Modify: `backend/app/services/dashboard_service.py`
- Modify: `backend/app/views/dashboard_view.py`
- Test: `backend/tests/test_dashboard_workbench_api.py`

**Step 1: Implement collection and response fields**

Query only visible projects and iterations whose workflow state category is `in_progress`. Convert their non-deleted requirements, tasks and Bugs with the existing `WorkbenchItem` mappers, deduplicate by object type and ID, and expose the list as `active_iteration_items` in `WorkbenchResponse`. Preserve every field needed by filtering, sorting and existing actions.

**Step 2: Verify the API contract passes**

Run: `pytest tests/test_dashboard_workbench_api.py -q`

Expected: PASS, including existing queue response behavior unless it is unused by the new UI.

### Task 3: Define frontend filtering and default sort behavior with failing tests

**Files:**
- Modify: `frontend/src/utils/workbenchViewModel.test.mjs`
- Modify: `frontend/src/utils/workbenchViewModel.js`

**Step 1: Add failing view-model tests**

Add representative active-iteration items for all three object types, including active, completed, cancelled, overdue, different priority levels, due dates and update times. Assert that the filtering helper supports keyword, project, iteration, type, status, priority, owner and handler values, and that the default sorter orders active before terminal, overdue before non-overdue, higher priority before lower priority, earlier due date before later/missing due dates, and newer updates last as the tiebreaker.

**Step 2: Run the focused test to verify it fails**

Run: `npm test workbenchViewModel`

Expected: FAIL because current helpers only support the source-queue filter model and do not implement the required sort order.

### Task 4: Implement the unified workbench view

**Files:**
- Modify: `frontend/src/utils/workbenchViewModel.js`
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/utils/workbenchViewModel.test.mjs`

**Step 1: Implement the view-model functions**

Add normalized option builders for project, iteration, status, priority, owner and handler, a single filtering function for `active_iteration_items`, and the deterministic default comparator. Keep `WorkflowActionButtons`, `resolveWorkbenchWorkflowCommand` and batch-assignment compatibility unchanged.

**Step 2: Replace queue controls with filter controls**

Remove the entry radio group, follow tabs and exception-only toolbar. Bind the single table directly to filtered and sorted active-iteration items. Add the required multi-select filters while retaining the keyword search and refresh action. Use static table labels rather than queue-dependent labels and remove queue-specific columns that have no meaning in the unified list.

**Step 3: Run the focused frontend test**

Run: `npm test workbenchViewModel`

Expected: PASS and output confirms unified filtering and sorting behavior.

### Task 5: Verify complete workbench behavior

**Files:**
- Test: `backend/tests/test_dashboard_workbench_api.py`
- Test: `frontend/src/utils/workbenchViewModel.test.mjs`

**Step 1: Run affected backend tests**

Run: `pytest tests/test_dashboard_workbench_api.py tests/test_current_handler_assignment_api.py tests/test_exception_center_api.py -q`

Expected: PASS.

**Step 2: Run all frontend tests and build**

Run: `npm test && npm run build`

Expected: all source tests pass and Vite completes without errors.

**Step 3: Perform a focused manual check**

Sign in as a user with access to multiple projects. Confirm the default table contains only work items in in-progress iterations, includes completed and cancelled rows after active rows, excludes unauthorized projects, and filters correctly by every available field.

**Step 4: Git handling**

Do not stage, commit, push, create a pull request, or merge. Request the required delivery instruction after implementation and verification.
