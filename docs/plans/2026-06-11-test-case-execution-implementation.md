# Test Case Execution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add direct test case execution with per-step results and history, and remove test case priority from the business surface.

**Architecture:** Keep existing test case CRUD. Add latest execution fields to `test_cases` and a separate execution log table. Frontend pages reuse one execution dialog pattern and call dedicated execution APIs.

**Tech Stack:** FastAPI, SQLAlchemy, MySQL runtime schema helper, Vue 3, Element Plus, Vite.

---

### Task 1: Backend Execution Model And Tests

**Files:**
- Create: `backend/app/models/test_case_execution.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/test_case.py`
- Modify: `backend/app/views/test_case_view.py`
- Modify: `backend/app/db/schema.py`
- Test: `backend/tests/test_test_case_execution_api.py`

**Steps:**
1. Write failing tests for execution creation, result calculation, execution history, and latest test case fields.
2. Add model and runtime schema.
3. Remove priority from test case API views.
4. Run focused tests until they pass.

### Task 2: Backend Execution APIs

**Files:**
- Modify: `backend/app/services/test_case_service.py`
- Modify: `backend/app/controllers/test_case_controller.py`
- Create or modify views in `backend/app/views/test_case_view.py`

**Steps:**
1. Add execution request/read view models.
2. Implement result calculation.
3. Implement create execution and list execution history.
4. Update latest execution fields on `test_cases`.

### Task 3: Frontend Execution UI

**Files:**
- Modify: `frontend/src/api/testCases.js`
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/views/TestsView.vue`
- Modify: `frontend/src/views/IterationDetailView.vue`

**Steps:**
1. Add API client methods.
2. Remove test case priority columns and form fields.
3. Add latest execution time/result columns.
4. Add Execute button.
5. Add execution dialog and history display.

### Task 4: Documentation

**Files:**
- Modify: `docs/prd/2026-06-09-intellective-bio-sdlc-prd.md`
- Modify: `docs/database/2026-06-09-intellective-bio-sdlc-data-dictionary-mysql.md`
- Modify: `docs/database/init_mysql.sql`

**Steps:**
1. Remove priority from test case field descriptions.
2. Document direct test case execution and result options.
3. Document latest execution fields and execution log table.

### Task 5: Verification And Commit

**Commands:**
- `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests/test_test_case_execution_api.py backend/tests/test_testing_bug_api.py -q`
- `npm run build` from `frontend`
- `git diff --check`
- `git status --short`

**Steps:**
1. Run backend tests.
2. Run frontend build.
3. Check whitespace.
4. Commit and push with message `feat: add test case execution history`.
