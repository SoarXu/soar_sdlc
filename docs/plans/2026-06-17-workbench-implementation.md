# Workbench Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an iteration-centered workbench where users can see, act on, and drag demand/task/test/Bug work items between iterations.

**Architecture:** Extend the existing dashboard module instead of adding a parallel entry. The backend provides one aggregate workbench endpoint and one move endpoint; frontend renders iteration boards and calls existing lifecycle APIs for actions.

**Tech Stack:** FastAPI, SQLAlchemy, MySQL, Vue 3, Element Plus, vue-draggable-plus, pytest, Vite.

---

### Task 1: PRD And Schema Contract

**Files:**
- Modify: `docs/prd/2026-06-09-intellective-bio-sdlc-prd.md`
- Modify: `docs/database/init_mysql.sql`
- Modify: `docs/database/2026-06-09-intellective-bio-sdlc-data-dictionary-mysql.md`

**Steps:**
1. Add workbench section with goals, display rules, lifecycle actions, drag move rules.
2. Add `test_cases.iteration_id` to SQL and data dictionary.
3. Commit with `docs: add workbench requirements`.

### Task 2: Backend Workbench API

**Files:**
- Modify: `backend/app/models/test_case.py`
- Modify: `backend/app/db/schema.py`
- Modify: `backend/app/views/dashboard_view.py`
- Modify: `backend/app/services/dashboard_service.py`
- Modify: `backend/app/controllers/dashboard_controller.py`
- Test: `backend/tests/test_dashboard_workbench_api.py`

**Steps:**
1. Write failing tests for aggregate workbench response and move endpoint.
2. Add `test_cases.iteration_id` model and runtime schema migration.
3. Implement `get_workbench` grouped by iteration.
4. Implement `move_workbench_item`.
5. Run target tests and commit with `feat: add workbench backend api`.

### Task 3: Frontend Workbench Board

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/src/api/dashboard.js`
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/styles.css`

**Steps:**
1. Install `vue-draggable-plus`.
2. Implement workbench board, filters, cards, and drag move call.
3. Wire lifecycle operation buttons to existing APIs.
4. Run `npm run build`.
5. Commit with `feat: add iteration workbench board`.

### Task 4: Verification Loop

**Files:**
- Review all changed files.

**Steps:**
1. Run `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests -q`.
2. Run `npm run build` in `frontend`.
3. Dispatch sub-agent to score coverage against the five user goals.
4. Fix gaps until score is at least 90.
5. Commit fixes and push.
