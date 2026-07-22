# Remove Workbench Unplanned Section Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the workbench unplanned section so normal requirements, tasks, and Bugs without an active iteration are visible only from project detail pages.

**Architecture:** Keep active-iteration and project-permission filtering in the backend as the single workbench scope boundary. Remove the `unplanned` response contract and all frontend consumers instead of hiding or returning an empty compatibility section. Preserve historical integrity exceptions independently of normal uniterated backlog items.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Pytest, Vue 3, Element Plus, Node test runner.

---

### Task 1: Revise The Approved PRD

**Files:**
- Modify: `docs/prd/2026-07-21-workbench-active-iteration-scope-prd.md`

**Step 1: Replace the workbench information architecture**

Remove the `待规划` entry, summary-card requirement, filters, scheduling actions, API field, acceptance criteria, test cases, release steps, and decision records that make uniterated items visible on the workbench.

State the replacement rule explicitly:

```text
未关联迭代的正常需求、任务和 Bug 不进入工作台任何正常入口；仅在项目详情中查看和排期。
```

Keep the distinction that uniterated data is not an exception by itself.

**Step 2: Verify the documentation has no stale product behavior**

Run:

```powershell
rg -n "待规划|unplanned|未纳入迭代.*工作台|未关联迭代.*工作台" docs/prd/2026-07-21-workbench-active-iteration-scope-prd.md
```

Expected: only explicit statements saying that the section is removed or uniterated normal items are excluded remain.

**Step 3: Commit the PRD revision**

```powershell
git add docs/prd/2026-07-21-workbench-active-iteration-scope-prd.md
git commit -m "docs: remove unplanned workbench scope"
```

### Task 2: Remove The Backend Unplanned Contract

**Files:**
- Modify: `backend/tests/test_dashboard_workbench_api.py`
- Modify: `backend/tests/test_current_handler_assignment_api.py`
- Modify: `backend/app/views/dashboard_view.py`
- Modify: `backend/app/services/dashboard_service.py`

**Step 1: Write failing backend tests**

Update the workbench tests to assert:

```python
assert "unplanned" not in response.json()
```

Create an uniterated non-terminal requirement, task, and Bug and assert that none appears in `pending_handling`, `unassigned`, `created_by_me`, `watched_by_me`, `mentioned_me`, or `exception_center` merely because it has no iteration.

Retain the tests proving active-iteration items appear and planning/terminal-iteration items do not.

**Step 2: Run tests and verify RED**

```powershell
$env:DATABASE_URL='mysql+pymysql://root:root123@127.0.0.1:3306/intellective_bio_sdlc?charset=utf8mb4'
python -m pytest backend/tests/test_dashboard_workbench_api.py backend/tests/test_current_handler_assignment_api.py -q
```

Expected: failures because `WorkbenchResponse` still returns `unplanned`.

**Step 3: Remove the backend field and query**

Delete:

- `WorkbenchResponse.unplanned`;
- `_unplanned_items`;
- `_can_schedule_project` if it has no other caller;
- the `unplanned_items` construction and owner collection;
- the `unplanned=WorkbenchSection(...)` response value;
- imports used only by the removed query.

Do not weaken active-iteration or project-scope filters for remaining sections.

**Step 4: Run tests and verify GREEN**

Run the Step 2 command.

Expected: all selected tests pass.

**Step 5: Commit the backend change**

```powershell
git add backend/app/views/dashboard_view.py backend/app/services/dashboard_service.py backend/tests/test_dashboard_workbench_api.py backend/tests/test_current_handler_assignment_api.py
git commit -m "feat: remove unplanned workbench response"
```

### Task 3: Remove The Frontend Entry And Summary

**Files:**
- Modify: `frontend/src/utils/workbenchViewModel.test.mjs`
- Modify: `frontend/src/components/workflowActionButtonsBehavior.test.mjs` only if shared assertions mention unplanned
- Modify: `frontend/src/utils/workbenchViewModel.js`
- Modify: `frontend/src/views/DashboardView.vue`

**Step 1: Write failing frontend tests**

Assert the exact entry order:

```javascript
assert.deepEqual(model.entryTabs.map((item) => item.key), [
  'pending_handling',
  'unassigned',
  'exception_center',
  'following'
])
```

Assert `summaryCards` and `queueSectionsByKey` do not contain `unplanned`, and source code exposes no history or iteration-range switch.

**Step 2: Run the test and verify RED**

```powershell
node frontend/src/utils/workbenchViewModel.test.mjs
```

Expected: failure because `unplanned` remains in the view model.

**Step 3: Remove frontend consumers**

Delete the unplanned tab, section normalization, summary card, section map entry, and Dashboard workflow-transition loading branch.

Keep existing shared tables, filters, workflow actions, and active-iteration empty-state behavior for remaining sections.

**Step 4: Run frontend tests and verify GREEN**

```powershell
node frontend/src/utils/workbenchViewModel.test.mjs
node frontend/src/components/workflowActionButtonsBehavior.test.mjs
```

Expected: both commands pass.

**Step 5: Compile modified Vue components**

Use `@vue/compiler-sfc` to parse and compile `DashboardView.vue` and `WorkflowActionButtons.vue`.

Expected: no parse, script, or template errors.

**Step 6: Commit the frontend change**

```powershell
git add frontend/src/utils/workbenchViewModel.js frontend/src/utils/workbenchViewModel.test.mjs frontend/src/views/DashboardView.vue
git commit -m "feat: remove unplanned workbench entry"
```

### Task 4: Full Regression And Contract Verification

**Files:**
- Verify all modified files.

**Step 1: Run the full backend suite**

```powershell
$env:DATABASE_URL='mysql+pymysql://root:root123@127.0.0.1:3306/intellective_bio_sdlc?charset=utf8mb4'
python -m pytest backend/tests -q
python -m compileall -q backend/app
```

Expected: all backend tests and Python compilation pass.

**Step 2: Run all directly executable frontend tests**

Run every `*.test.mjs` except `workflowEdgePath.test.mjs` when the managed environment still blocks its child process.

Expected: all selected tests pass.

**Step 3: Compile every Vue SFC**

Parse and compile all files under `frontend/src/**/*.vue` with `@vue/compiler-sfc`.

Expected: every component compiles.

**Step 4: Attempt formal frontend test and build commands**

```powershell
npm --prefix frontend test
npm --prefix frontend run build
```

Expected outside the managed child-process restriction: both pass. If `spawn EPERM` occurs before source compilation, report it as an environment blocker and retain direct-test plus SFC-compile evidence.

**Step 5: Run repository hygiene checks**

```powershell
git diff --check
git status --short
```

Also scan untracked changed files for trailing whitespace.

**Step 6: Verify the live contract after integration**

Restart the backend from the integrated branch and inspect `/openapi.json`.

Expected: `WorkbenchResponse` has no `unplanned` property. Verify an uniterated normal requirement is absent from all workbench sections while remaining visible in project detail.

**Step 7: Commit final verification-only adjustments if required**

Only commit files changed to correct a verified failure. Do not create metadata-only churn.
