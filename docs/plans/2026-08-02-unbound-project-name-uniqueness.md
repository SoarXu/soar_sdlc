# Unbound Project Name Uniqueness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent duplicate project names within the same unbound project hierarchy.

**Architecture:** Reuse the existing service-level uniqueness query for null `program_id` values, preserving the current sibling `parent_id` scope. No frontend behavior changes are required because both project-save views already present backend validation messages.

**Tech Stack:** FastAPI, SQLAlchemy, pytest.

### Task 1: Cover unbound sibling conflicts

**Files:**
- Modify: `backend/tests/test_project_name_uniqueness.py`
- Modify: `backend/app/services/project_service.py`

**Step 1: Write the failing test**

Create an unbound root project, then submit a second root project with the same
name and assert the API responds with HTTP 422 and `项目名称已存在`.

**Step 2: Run the focused test**

Run: `python -m pytest tests/test_project_name_uniqueness.py -q`

Expected: FAIL because unbound projects currently bypass the validation.

**Step 3: Implement the minimal change**

Remove the early return for null `program_id` so the existing query applies its
null program and matching-parent filters.

**Step 4: Re-run the focused test**

Run: `python -m pytest tests/test_project_name_uniqueness.py -q`

Expected: exit code 0.

### Task 2: Verify regression safety

**Files:**
- Modify: no additional files expected

**Step 1: Run backend acceptance tests**

Run: `python -m pytest tests/test_project_name_uniqueness.py -q`

Expected: exit code 0, including the existing different-parent allowance.

**Step 2: Commit**

Do not commit automatically. Request the required delivery confirmation after
reporting verified local changes.
