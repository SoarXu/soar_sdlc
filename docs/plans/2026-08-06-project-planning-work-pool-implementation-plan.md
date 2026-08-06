# 项目待规划工作池 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make each project's default requirement-pool iteration a visible, authoritative planning work pool for unallocated requirements, tasks, and Bugs, without changing the workbench.

**Architecture:** Reuse the canonical project pool identifiers already owned by `requirement_pool_service`. Centralize default-iteration resolution and pool-state validation in backend services; expose project-scoped work-pool counts with project iteration data; render project-only summary and filters in the existing project detail view.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic data migration, pytest, Vue 3, Element Plus, Node assert tests, Vite.

---

### Task 1: Define project work-pool statistics

**Files:**
- Modify: `backend/app/services/requirement_pool_service.py`
- Modify: `backend/app/views/project_view.py`
- Modify: project iteration query service/router found by `rg "ProjectIterationPage" backend/app`
- Test: add focused cases to `backend/tests/test_project_requirement_pool_api.py`

**Step 1: Write failing API tests**

Create a project with its work pool, add non-terminal requirements, tasks, and Bugs bound to the pool, and assert the project iteration response includes the pool ID plus separate counts. Add a terminal pool item through controlled fixture setup and assert it is excluded.

**Step 2: Verify RED**

Run: `pytest tests/test_project_requirement_pool_api.py -k work_pool_summary -v`

Expected: FAIL because no project work-pool summary exists.

**Step 3: Implement minimal summary query and response model**

Add a `ProjectWorkPoolSummary` response with `iteration_id`, `requirement_count`, `task_count`, `bug_count`, and `total_count`. Count only non-deleted, non-terminal items whose `iteration_id` equals the canonical project pool.

**Step 4: Verify GREEN**

Run: `pytest tests/test_project_requirement_pool_api.py -k work_pool_summary -v`

Expected: PASS.

### Task 2: Give all new work items a default pool

**Files:**
- Modify: `backend/app/services/requirement_pool_service.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/services/bug_service.py`
- Test: `backend/tests/test_project_requirement_pool_api.py`, `backend/tests/test_task_api.py`, `backend/tests/test_bug_workflow_api.py`

**Step 1: Write failing tests**

Cover these cases independently:

- direct task without `iteration_id` receives the project pool;
- direct Bug without `iteration_id` receives the project pool;
- task created from a requirement inherits the requirement iteration;
- Bug linked to a requirement or task in a delivery iteration inherits that iteration, otherwise receives the pool.

**Step 2: Verify RED**

Run the named tests with `pytest -v`.

**Step 3: Implement one default-resolution helper**

Keep `resolve_requirement_iteration_id` for requirement semantics and add a small shared resolver for task/Bug creation that validates explicit iterations, prefers an eligible source item's delivery iteration, and otherwise returns the canonical project pool.

**Step 4: Verify GREEN**

Run the focused task, Bug, and work-pool tests.

### Task 3: Prevent execution inside the work pool

**Files:**
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/services/iteration_service.py`
- Test: `backend/tests/test_workflow_runtime_api.py` and `backend/tests/test_project_requirement_pool_api.py`

**Step 1: Write failing workflow tests**

For each of requirement, task, and Bug in the pool, attempt the first execution transition without a target delivery iteration. Assert a Chinese `TARGET_ITERATION_REQUIRED` contract. Submit the transition with a planning or active delivery iteration and assert item migration and successful transition are committed together.

**Step 2: Verify RED**

Run only the new tests with `pytest -v`.

**Step 3: Implement the transition guard**

At runtime transition preparation, detect pool membership for each work-item type. Require a mutable non-pool delivery iteration for execution transitions, lock it with the item, move the item, and then execute the existing transition path. Preserve requirement-to-task synchronization and do not force unrelated Bugs to move.

**Step 4: Verify GREEN**

Run the focused workflow and iteration tests.

### Task 4: Backfill legacy unallocated work

**Files:**
- Create: `backend/alembic/versions/<revision>_backfill_project_work_pool_items.py`
- Create or modify: `backend/scripts/backfill_project_work_pool_items.py`
- Test: migration/service test adjacent to existing Alembic migration tests

**Step 1: Write failing migration test**

Seed projects with nullable task/Bug iteration IDs and one terminal pool item. Assert the migration assigns only null non-terminal task/Bug records to their canonical pool, leaves explicit delivery iterations unchanged, and emits terminal-pool anomalies.

**Step 2: Verify RED**

Run the focused migration test.

**Step 3: Implement idempotent backfill**

Resolve each item's project pool, update only null iteration IDs, create history records consistently with existing membership helpers, and write a deterministic anomaly report for terminal pool items without inventing historical delivery iterations.

**Step 4: Verify GREEN**

Run the migration test twice and confirm the second run has no additional updates.

### Task 5: Render project-only planning views

**Files:**
- Modify: `frontend/src/api/projects.js`
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: project work-item list/filter components used by the project detail view
- Test: create `frontend/src/views/projectPlanningWorkPool.test.mjs`

**Step 1: Write failing source-contract tests**

Assert the project detail consumes the work-pool summary, renders a top information band in overview and iterations, exposes counts for requirements/tasks/Bugs, and passes the canonical pool ID into project-local filters. Assert `DashboardView.vue` is not changed by this feature.

**Step 2: Verify RED**

Run: `npm test -- projectPlanningWorkPool`

Expected: FAIL because no planning-work-pool UI exists.

**Step 3: Implement project views**

Add the full-width information band and project-local filter option. Reuse existing iteration-selection and batch-move flows for “纳入迭代”; do not add a workbench tab, card, or filter.

**Step 4: Verify GREEN**

Run: `npm test -- projectPlanningWorkPool`

Expected: PASS.

### Task 6: Complete regression verification

**Files:**
- Verify: affected backend and frontend tests

**Step 1: Run backend regression suites**

Run the focused project, task, Bug, iteration, workflow runtime, and migration tests, then `pytest` as time permits.

**Step 2: Run frontend test suite**

Run: `npm test`

**Step 3: Build frontend**

Run: `npm run build`

**Step 4: Inspect migration and UI behavior**

Apply the migration in a development database, inspect the anomaly report, and use the project detail page to verify counts update after creating and moving each of the three work-item types.
