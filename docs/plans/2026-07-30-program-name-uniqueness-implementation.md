# 项目集名称唯一性 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enforce active program-name uniqueness within each parent scope, including the root scope.

**Architecture:** Centralize name normalization and conflict checks in `program_service`. Add MySQL generated scope/name columns plus a unique index as the concurrency backstop; runtime schema setup and an Alembic migration install the same database contract.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, MySQL 8, SQLite, Pytest.

---

### Task 1: Add failing service and API tests

**Files:**
- Modify: `backend/tests/test_program_project_api.py`
- Create: `backend/tests/test_program_name_uniqueness.py`

**Step 1: Write failing behavior tests**

Cover root duplicates, sibling duplicates, different-parent allowance, trim and case
normalization, reuse after soft deletion, rename conflict, and parent-move conflict.
Add a MySQL DDL contract assertion for the generated columns and unique index.

**Step 2: Run the focused tests**

Run: `E:\miniforge3\python.exe -m pytest tests/test_program_name_uniqueness.py tests/test_program_project_api.py -q`

Expected: FAIL because no name conflict validation or unique index exists.

### Task 2: Implement service-side normalization and validation

**Files:**
- Modify: `backend/app/services/program_service.py`
- Test: `backend/tests/test_program_name_uniqueness.py`

**Step 1: Normalize names at the service boundary**

Strip leading and trailing whitespace. Reject an empty result with HTTP 422.

**Step 2: Check active records in the effective parent scope**

Before create and update, query active records by parent scope and case-insensitive
normalized name, excluding the record under update. Raise HTTP 422 on conflict.

**Step 3: Run focused tests**

Expected: PASS.

### Task 3: Add the MySQL concurrency constraint

**Files:**
- Modify: `backend/app/db/schema.py`
- Create: `backend/alembic/versions/<revision>_program_name_uniqueness.py`
- Test: `backend/tests/test_program_name_uniqueness.py`

**Step 1: Add failing schema-contract test**

Assert MySQL schema setup adds generated active scope/name columns and a unique index.

**Step 2: Implement idempotent runtime and Alembic DDL**

Use generated columns that produce NULL for deleted rows and map root scope to 0;
create a unique index over both columns. Preserve SQLite compatibility by skipping
MySQL-only generated-column DDL.

**Step 3: Run focused tests**

Expected: PASS.

### Task 4: Verify behavior and integration

**Files:**
- Verify: changed files

**Step 1: Run focused backend tests**

Run: `E:\miniforge3\python.exe -m pytest tests/test_program_name_uniqueness.py tests/test_program_project_api.py -q`

**Step 2: Run migration/schema verification against MySQL**

Run Alembic upgrade and query `SHOW CREATE TABLE programs`.

**Step 3: Inspect scope**

Run: `git diff --check && git status --short`.
