# Test Case Bug Iteration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build the failed/blocked test case to Bug workflow and align iteration detail lists with project detail behavior.

**Architecture:** Add a backend service endpoint that creates a Bug from a failed or blocked test case using the latest execution log as the source. Extend iteration detail payloads with Bugs, and reuse existing frontend list patterns for project and iteration contexts.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, MySQL-compatible schema patching, Vue 3, Element Plus, Axios.

---

### Task 1: Backend Schema And Models

**Files:**
- Modify: `backend/app/models/bug.py`
- Modify: `backend/app/views/bug_view.py`
- Modify: `backend/app/db/schema.py`
- Modify: `docs/database/init_mysql.sql`
- Modify: `docs/database/2026-06-09-intellective-bio-sdlc-data-dictionary-mysql.md`

**Steps:**

1. Add `iteration_id` and `bug_type` to the Bug SQLAlchemy model.
2. Add matching fields to `BugBase`, `BugUpdate`, and `BugRead`.
3. Add schema patching for existing databases.
4. Update SQL initialization and data dictionary.
5. Run backend tests that load models.

### Task 2: Backend Bug Creation From Test Case

**Files:**
- Modify: `backend/app/views/test_case_view.py`
- Modify: `backend/app/services/test_case_service.py`
- Modify: `backend/app/controllers/test_case_controller.py`
- Test: `backend/tests/test_test_case_execution_api.py`

**Steps:**

1. Add request schema for Bug creation from a test case.
2. Implement `create_bug_from_test_case`.
3. Validate latest result is `failed` or `blocked`.
4. Build default rich-text reproduce steps from the latest execution log.
5. Infer requirement, project, iteration, and owner.
6. Add API route `POST /test-cases/{test_case_id}/bugs`.
7. Add tests for success and rejected passed case.

### Task 3: Iteration Detail Bug Payload

**Files:**
- Modify: `backend/app/services/iteration_service.py`
- Modify: `backend/app/controllers/iteration_controller.py` if response shape requires changes
- Test: `backend/tests/test_iteration_detail_api.py` or nearest existing iteration test

**Steps:**

1. Include Bugs linked to the iteration in detail payload.
2. Ensure Bug objects include names needed by frontend through existing lookup lists or raw IDs.
3. Add backend test that a Bug created from a linked failed use case appears in iteration detail.

### Task 4: Frontend API

**Files:**
- Modify: `frontend/src/api/testCases.js`
- Modify: `frontend/src/api/bugs.js` if shared helpers are needed

**Steps:**

1. Add `createBugFromTestCase(id, payload)`.
2. Keep API shape aligned with backend request schema.

### Task 5: Frontend Shared Constants And Helpers

**Files:**
- Modify existing Vue files directly unless a local constants module already exists.
- Likely modify: `frontend/src/views/TestsView.vue`
- Likely modify: `frontend/src/views/ProjectDetailView.vue`
- Likely modify: `frontend/src/views/IterationDetailView.vue`

**Steps:**

1. Add Bug type options.
2. Reuse priority decoration options for Bug severity and priority.
3. Add helper that enables Bug button only for `failed` or `blocked`.
4. Add helper to build or display rich-text reproduce steps.

### Task 6: Frontend Test Case Submit Bug Dialog

**Files:**
- Modify: `frontend/src/views/TestsView.vue`
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/views/IterationDetailView.vue`

**Steps:**

1. Add submit Bug button in test case operation columns.
2. Add submit Bug dialog with title, type, severity, priority, and reproduce steps.
3. Use rich-text-capable HTML content field; file upload is intentionally excluded.
4. Submit through `createBugFromTestCase`.
5. Refresh lists after success.

### Task 7: Frontend Auto Advance Execution

**Files:**
- Modify: `frontend/src/views/TestsView.vue`
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/views/IterationDetailView.vue`

**Steps:**

1. After saving execution, find the next test case in the current visible list.
2. If next exists, open execution dialog for that test case.
3. If next does not exist, close the dialog.
4. Refresh execution history and lists.

### Task 8: Iteration Detail Lists

**Files:**
- Modify: `frontend/src/views/IterationDetailView.vue`
- Modify: `frontend/src/router/index.js` if return behavior needs route metadata
- Modify: `frontend/src/views/RequirementDetailView.vue`
- Modify: task detail view if present

**Steps:**

1. Add Bug tab and table.
2. Expand requirement table fields and operations to match project detail.
3. Expand task table fields and operations to match project detail, grouped by project.
4. Add query params for returning to iteration detail requirement/task tab.
5. Make title links preserve return target.

### Task 9: Verification And Commit

**Commands:**

1. Run backend focused tests:
   `E:\\miniconda3\\envs\\soar_sdlc_py311\\python.exe -m pytest backend/tests/test_test_case_execution_api.py backend/tests/test_testing_bug_api.py -q`
2. Run frontend build:
   `npm run build`
3. Run whitespace check:
   `git diff --check`
4. Commit and push:
   `git add .`
   `git commit -m "feat: create bugs from failed test cases"`
   `git -c http.version=HTTP/1.1 push`
