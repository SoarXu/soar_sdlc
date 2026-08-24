# Workbench Server Pagination Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep workbench loading bounded by page size through database filtering/pagination and current-page-only workflow action loading.

**Architecture:** Add a dedicated paginated active-iteration work-item query while preserving the legacy aggregate endpoint. Project requirement, task, and Bug rows into one SQL union, apply scope and filters once, and return facets plus a stable page for direct frontend consumption.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, Vue 3, Axios, Element Plus, Node.js contract tests, Vite.

---

### Task 1: Backend paging contract

**Files:**
- Modify: `backend/app/views/dashboard_view.py`
- Modify: `backend/app/controllers/dashboard_controller.py`
- Modify: `backend/app/services/dashboard_service.py`
- Modify: `backend/tests/test_dashboard_workbench_api.py`

1. Add failing tests for 120 rows, page size 20, filters, permissions and stable page boundaries.
2. Run the focused tests and verify the new route returns 404 before implementation.
3. Add page/facet response models and controller query parameters.
4. Implement a SQL union query, count, stable ordering and facets without changing `get_workbench()`.
5. Run focused and full dashboard tests.

### Task 2: Frontend server paging contract

**Files:**
- Modify: `frontend/src/api/dashboard.js`
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/utils/workbenchViewModel.test.mjs`

1. Add failing source-contract assertions that the page calls `/dashboard/workbench/items`, sends page/filter parameters and loads actions from response `items` only.
2. Verify RED with `node src/utils/workbenchViewModel.test.mjs`.
3. Replace client-side filtering/pagination with server response state and debounced reload.
4. Preserve current filters, pagination, refresh and batch mutation behavior.
5. Verify focused tests and production build.

### Task 3: Performance and regression verification

**Files:**
- Modify after evidence: `docs/issues/2026-08-22-后续问题清单.md`

1. Run paginated API tests with 120+ rows and assert response cardinality/total.
2. Run the existing workbench API suite to prove legacy compatibility.
3. Run frontend full tests and build.
4. Record commands, counts and observed payload bounds in N-007.
5. Do not commit until the required delivery option is selected.
