# Iteration Scope Detail Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add iteration detail management for linked requirements, direct task links, derived test cases, and overview metrics.

**Architecture:** Keep `iteration_projects` as iteration scope. Use `requirements.iteration_id` for requirement membership and add `tasks.iteration_id` only for direct task membership. Build backend detail/link APIs and a new Vue iteration detail page that groups requirements by scoped project tree.

**Tech Stack:** FastAPI, SQLAlchemy, MySQL runtime schema helper, Vue 3, Element Plus, Vite.

---

### Task 1: Backend Data Model And Tests

**Files:**
- Modify: `backend/app/models/task.py`
- Modify: `backend/app/views/task_view.py`
- Modify: `backend/app/db/schema.py`
- Test: `backend/tests/test_iteration_detail_api.py`

**Steps:**
1. Add failing backend tests for iteration detail scope, available requirements, direct task linking, removal, and metrics.
2. Run the focused test to verify failures.
3. Add `tasks.iteration_id` to model/view/schema.
4. Run the focused test again and continue to Task 2 failures.

### Task 2: Backend Iteration Detail APIs

**Files:**
- Modify: `backend/app/services/iteration_service.py`
- Modify: `backend/app/controllers/iteration_controller.py`
- Create or modify view models in `backend/app/views/iteration_view.py`
- Test: `backend/tests/test_iteration_detail_api.py`

**Steps:**
1. Implement helpers to collect iteration linked project IDs and descendant project IDs.
2. Implement `get_iteration_detail`.
3. Implement available requirement and task queries.
4. Implement link/unlink requirement APIs.
5. Implement link/unlink direct task APIs.
6. Run backend tests and make them pass.

### Task 3: Frontend Iteration Detail Page

**Files:**
- Modify: `frontend/src/api/iterations.js`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/views/IterationsView.vue`
- Create: `frontend/src/views/IterationDetailView.vue`

**Steps:**
1. Add API client methods for detail, available requirements/tasks, link, and unlink.
2. Add route `/iterations/:id`.
3. Make iteration name links navigate to detail.
4. Build detail page tabs: overview, requirements, tasks, cases.
5. Add link dialogs and remove actions.
6. Render requirements grouped by project tree.
7. Render overview coverage and progress metrics.

### Task 4: Documentation

**Files:**
- Modify: `docs/prd/2026-06-09-intellective-bio-sdlc-prd.md`
- Modify: `docs/database/2026-06-09-intellective-bio-sdlc-data-dictionary-mysql.md`
- Modify: `docs/database/init_mysql.sql`

**Steps:**
1. Document iteration detail tabs and linking behavior.
2. Document direct task iteration link.
3. Document metrics formulas.
4. Add `tasks.iteration_id` to database docs and init SQL.

### Task 5: Verification And Commit

**Commands:**
- `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests/test_iteration_detail_api.py backend/tests/test_requirement_task_api.py -q`
- `npm run build` from `frontend`
- `git diff --check`
- `git status --short`

**Steps:**
1. Run backend tests.
2. Run frontend build.
3. Check whitespace.
4. Commit and push with message `feat: add iteration detail scope management`.
