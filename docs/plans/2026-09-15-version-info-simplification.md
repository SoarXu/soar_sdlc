# Version Information Simplification Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reduce runtime version information to frontend/backend versions and their comparison status.

**Architecture:** Make the backend version route independent of the database and omit commit and migration fields. Remove their frontend display and compare only semantic version numbers, leaving package metadata untouched.

**Tech Stack:** FastAPI, Vue 3, Element Plus, pytest, Node tests, Vite.

---

### Task 1: Backend Version Contract

**Files:** `backend/tests/test_health.py`, `backend/app/controllers/health_controller.py`

1. Replace the revision tests with an exact two-field response assertion and a test that overrides `get_db` with a failing dependency; assert the request still returns 200.
2. Run `E:\miniforge3\python.exe -m pytest tests/test_health.py -q` against an isolated MySQL `_test` database; verify the new tests fail for the existing route.
3. Remove the `get_db` dependency, revision SQL, and `git_commit` field. Return `app_version` and `environment` only.
4. Re-run the focused tests; expect all to pass.

### Task 2: Frontend Version Dialog

**Files:** `frontend/src/layout/runtimeVersion.test.mjs`, `frontend/src/utils/versionStatus.test.mjs`, `frontend/src/layout/MainLayout.vue`, `frontend/src/utils/versionStatus.js`

1. Assert the dialog contains three version/status rows and no commit/database rows or frontend commit reference; assert version-only status values and an accurate unavailable label.
2. Run the focused Node tests and verify expected failures.
3. Remove commit/database rows and frontend commit usage; compare only versions and show `版本信息无法获取` on request failure.
4. Run `npm test` and `npm run build` in `frontend/`.

### Task 3: Runtime Verification

1. Restart the local backend on port 8000 with the changed source, keeping port 8001 stopped.
2. Request `/api/v1/version` through ports 8000 and 5173 and verify the reduced response.
3. Check `git diff --check`, report tests and Git delivery options. Do not commit or push without user confirmation.
