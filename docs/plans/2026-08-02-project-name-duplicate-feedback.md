# Project Name Duplicate Feedback Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Present duplicate project names as recoverable Chinese non-modal messages in every project form without altering the established hierarchy-scoped uniqueness rule.

**Architecture:** Retain the backend's existing `program_id` plus `parent_id` uniqueness scope. Add small frontend catch blocks around the two form submit flows that use the same non-modal `ElMessage.error` feedback as project-set saves and preserve the dialog state on failure.

**Tech Stack:** FastAPI, SQLAlchemy, Vue 3, Element Plus, Node `assert` tests, pytest.

### Task 1: Lock the server uniqueness scope

**Files:**
- Modify: `backend/tests/test_project_name_uniqueness.py`
- Modify: no production backend files expected

**Step 1: Write failing API cases**

Create one project in a program, then assert a same-name sibling returns HTTP 422 with `项目名称已存在`. Create a second program and assert the same project name is accepted there.

**Step 2: Run the focused test**

Run: `pytest tests/test_project_name_uniqueness.py -q`

Expected: the new acceptance case fails if uniqueness accidentally spans programs.

**Step 3: Preserve or minimally correct server scope**

Keep `_require_unique_project_name` scoped by `program_id` and `parent_id`; make a production change only if the new test exposes a mismatch.

**Step 4: Re-run the focused test**

Run: `pytest tests/test_project_name_uniqueness.py -q`

Expected: exit code 0.

### Task 2: Handle duplicate save errors in both views

**Files:**
- Create: `frontend/src/views/projectDuplicateNameFeedback.test.mjs`
- Modify: `frontend/src/views/ProgramsView.vue`
- Modify: `frontend/src/views/ProjectsView.vue`

**Step 1: Write failing source-contract assertions**

Require each `submitProject` function to catch errors and pass them through `actionErrorMessage` to `ElMessage.error` with a project-save fallback.

**Step 2: Run the focused test**

Run: `npm test -- projectduplicatenamefeedback`

Expected: FAIL because the current submit functions have no `catch`.

**Step 3: Add minimal catch blocks**

Call `ElMessage.error(actionErrorMessage(error, '项目保存失败'))` from each catch without closing the dialog or resetting the form. Leave success behavior unchanged.

**Step 4: Re-run focused frontend tests**

Run: `npm test -- projectduplicatenamefeedback`

Expected: exit code 0.

### Task 3: Verify the change

**Files:**
- Modify: no additional files expected

**Step 1: Run the full frontend suite**

Run: `npm test`

Expected: exit code 0.

**Step 2: Build the frontend**

Run: `npm run build`

Expected: Vite exits with code 0.

**Step 3: Run the focused backend test**

Run: `pytest tests/test_project_name_uniqueness.py -q`

Expected: exit code 0.

**Step 4: Commit**

Do not commit automatically. Request the required delivery confirmation after reporting verified local changes.
