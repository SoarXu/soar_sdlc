# Workflow Runtime Batch Performance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce workbench, program, and project page loading from thousands of repeated SQL queries to bounded batch queries without changing permissions or response contracts.

**Architecture:** Coordinate default templates once per batch request, add a request-scoped transition loading context for shared data, and replace per-project member HTTP requests with one batch endpoint. Keep single-object APIs compatible and add slow-request database query metrics.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, Vue 3, Axios, Node source-contract tests

---

### Task 1: Prevent repeated template coordination

**Files:**
- Modify: `backend/app/services/workflow_runtime_service.py`
- Test: `backend/tests/test_workflow_runtime_api.py`

1. Add a failing test that patches `ensure_default_workflow_templates` and asserts one invocation for a multi-item batch.
2. Run the focused test and confirm it fails with one invocation per item.
3. Add a private transition-listing path that accepts an already-prepared batch context and skips template coordination.
4. Run the focused test and existing workflow runtime tests.

### Task 2: Bound batch transition SQL queries

**Files:**
- Modify: `backend/app/services/workflow_runtime_service.py`
- Test: `backend/tests/test_workflow_runtime_api.py`

1. Add a failing SQL query-count test for a representative multi-item batch.
2. Add request-scoped caches/prefetch for repeated definition, state, transition, permission, role, project-member and component-route reads.
3. Compare batch results with single-item results in tests.
4. Run workflow runtime and permission regression tests.

### Task 3: Add project-member batch loading

**Files:**
- Modify: `backend/app/controllers/project_controller.py`
- Modify: `backend/app/services/project_service.py`
- Modify: `backend/app/views/project_view.py`
- Test: `backend/tests/test_project_permission_boundary_api.py`

1. Add failing tests for grouped member results, empty input and project visibility.
2. Implement the batch request/response schema, controller and service query.
3. Keep the existing per-project member endpoint unchanged.
4. Run project permission and governance tests.

### Task 4: Remove frontend member N+1 and scope project actions

**Files:**
- Modify: `frontend/src/api/projects.js`
- Modify: `frontend/src/views/ProjectsView.vue`
- Modify: `frontend/src/views/ProgramsView.vue`
- Test: `frontend/src/views/projectsViewPerformance.test.mjs`

1. Add failing source-contract tests asserting one batch member request and current-page project action IDs.
2. Add the batch API client and replace per-project `Promise.all` calls.
3. Derive visible project IDs from the paged project tree and watch pagination changes to reload actions.
4. Run focused frontend tests and the full frontend suite.

### Task 5: Add slow API database metrics

**Files:**
- Modify: `backend/app/main.py`
- Modify: `backend/app/db/session.py`
- Modify: `backend/app/core/config.py`
- Test: `backend/tests/test_db_session.py`

1. Add failing tests for request-scoped query count/time aggregation and sanitized slow-request logging.
2. Implement SQLAlchemy timing hooks and API middleware with a configurable threshold.
3. Confirm logs omit SQL text, parameters and authorization data.
4. Run database session and health tests.

### Task 6: End-to-end verification

**Files:**
- Verify: `backend/app/services/workflow_runtime_service.py`
- Verify: `frontend/src/views/DashboardView.vue`
- Verify: `frontend/src/views/ProgramsView.vue`
- Verify: `frontend/src/views/ProjectsView.vue`

1. Run focused backend suites for workflow runtime, workbench pagination and project permissions.
2. Run the full frontend test suite and production build.
3. Repeat the read-only SQL profiler and record before/after query counts and timings.
4. Recheck project, project set and workbench pages in the browser.

Git commits are intentionally deferred until the repository owner selects a delivery option required by `AGENTS.md`.
