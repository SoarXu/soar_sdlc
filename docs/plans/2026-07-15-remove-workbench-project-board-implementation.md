# Workbench Project Board Removal Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Completely remove the workbench project board UI, response data, aggregation code, and tests while preserving all other workbench features.

**Architecture:** Remove the feature from both sides of the existing `GET /dashboard/workbench` contract. The frontend view model and page will only consume queue sections, while the backend service will stop querying and serializing project-board items.

**Tech Stack:** Vue 3, Element Plus, Node test runner, FastAPI, Pydantic, SQLAlchemy, pytest

---

### Task 1: Remove the project board from the frontend view model

**Files:**
- Modify: `frontend/src/utils/workbenchViewModel.test.mjs:1-180`
- Modify: `frontend/src/utils/workbenchViewModel.js:1-220`

**Step 1: Update the view-model test to define the removed contract**

Remove the `buildProjectBoard` import and its dedicated grouping test. Remove `project_board` from the fixture, then assert that the remaining entry keys and metrics are exactly:

```js
assert.deepEqual(viewModel.entryTabs.map((item) => item.key), [
  'pending_handling',
  'unassigned',
  'exception_center',
  'tracking'
])
assert.deepEqual(viewModel.metrics.map((item) => item.key), [
  'pending_handling',
  'unassigned',
  'exception_center',
  'tracking'
])
```

Delete the workflow-action assertion that uses the removed `project_board` section.

**Step 2: Run the focused test and verify it fails**

Run: `node --test frontend/src/utils/workbenchViewModel.test.mjs`

Expected: FAIL because the production view model still returns `project_board` in entry tabs and metrics.

**Step 3: Remove project-board view-model code**

In `workbenchViewModel.js`:

- Remove the `project_board` entry from `ENTRY_TABS`.
- Remove parsing and returned properties for board items, board dimensions, board label, and owner/handler board metadata.
- Remove the `project_board` metric.
- Remove the exported `buildProjectBoard` function and helpers used only by it.
- Keep queue filtering, status labels, action helpers, and tracking-section behavior unchanged.

**Step 4: Run the focused test and verify it passes**

Run: `node --test frontend/src/utils/workbenchViewModel.test.mjs`

Expected: PASS.

### Task 2: Remove the project board page UI

**Files:**
- Modify: `frontend/src/views/DashboardView.vue:1-855`

**Step 1: Remove the project-board template branch**

- Change the queue list wrapper from `v-if="activeView !== 'project_board'"` to an unconditional list wrapper.
- Delete the `v-else` project-board toolbar, empty state, grouped cards, and workflow buttons.
- Preserve the exception-center filter toolbar and queue table.

**Step 2: Remove project-board script state and computations**

- Remove `buildProjectBoard` and `typeShortLabel` imports if no remaining code uses them.
- Remove board grouping/filter refs and all board option/group computed values.
- Remove `openIterationDetail` and any board-only option helper that has no remaining consumer.
- Remove `project_board` from `loadWorkflowTransitions`; only retained queue sections may request transitions.
- Preserve test-run detail routing, Bug type loading, exception filters, and shared work-item actions.

**Step 3: Remove project-board styles**

Delete all scoped selectors beginning with `.project-board-` and the media rule that only adjusts project-board elements. Preserve exception-filter styles.

**Step 4: Run frontend tests and build**

Run: `npm test`

Working directory: `frontend`

Expected: all tests PASS.

Run: `npm run build`

Working directory: `frontend`

Expected: Vite build completes without unused imports or template errors.

### Task 3: Remove project-board data from the backend API

**Files:**
- Modify: `backend/tests/test_dashboard_workbench_api.py:100-410`
- Modify: `backend/app/views/dashboard_view.py:55-72`
- Modify: `backend/app/services/dashboard_service.py:1-360`

**Step 1: Update API tests to define the removed response field**

Replace project-board assertions in the general workbench response tests with:

```python
assert "project_board" not in data
```

Rename any test whose name includes `project_board` when its remaining assertions cover created, watched, mentioned, or exception sections. Delete the two tests dedicated only to project-board normalization, uniterated grouping, and terminal-item retention. Preserve setup and assertions used by other workbench sections.

**Step 2: Run the focused backend test and verify it fails**

Run: `pytest tests/test_dashboard_workbench_api.py -q`

Working directory: `backend`

Expected: FAIL because `WorkbenchResponse` still serializes `project_board`.

**Step 3: Remove the project-board response model**

In `dashboard_view.py`, delete `WorkbenchProjectBoardSection` and remove the `project_board` field from `WorkbenchResponse`. Keep `WorkbenchSection`, owners, review tasks, role keys, and view mode unchanged.

**Step 4: Remove project-board aggregation**

In `dashboard_service.py`:

- Remove the `WorkbenchProjectBoardSection` import.
- Remove the `_project_board_items` call and the `project_board=` response construction.
- Remove `_project_board_items` and `_project_board_group_dimensions`.
- Remove imports and local values that become unused only because of this deletion.
- Preserve queue item construction, exception evaluation, role scoping, owners, review tasks, and iteration-name enrichment.

**Step 5: Run the focused backend test and verify it passes**

Run: `pytest tests/test_dashboard_workbench_api.py -q`

Working directory: `backend`

Expected: PASS.

### Task 4: Verify the complete removal

**Files:**
- Verify: `frontend/src/views/DashboardView.vue`
- Verify: `frontend/src/utils/workbenchViewModel.js`
- Verify: `backend/app/views/dashboard_view.py`
- Verify: `backend/app/services/dashboard_service.py`
- Verify: related tests

**Step 1: Scan runtime code for remnants**

Run:

```powershell
rg -n -S "project_board|buildProjectBoard|WorkbenchProjectBoardSection|项目看板|看板工作项" backend/app frontend/src
```

Expected: no matches.

**Step 2: Run frontend verification**

Run: `npm test`

Working directory: `frontend`

Expected: all tests PASS.

Run: `npm run build`

Working directory: `frontend`

Expected: build succeeds.

**Step 3: Run backend workbench verification**

Run: `pytest tests/test_dashboard_workbench_api.py tests/test_exception_center_api.py tests/test_unassigned_work_items_api.py -q`

Working directory: `backend`

Expected: all selected tests PASS.

**Step 4: Review the final diff**

Run:

```powershell
git diff --check
git diff -- frontend/src/views/DashboardView.vue frontend/src/utils/workbenchViewModel.js frontend/src/utils/workbenchViewModel.test.mjs backend/app/views/dashboard_view.py backend/app/services/dashboard_service.py backend/tests/test_dashboard_workbench_api.py
```

Expected: only project-board-specific code and assertions are removed; unrelated dirty-worktree changes remain intact.
