# Code Review Status Rename Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rename the requirement, task, and Bug review state from “待评审” to `Code Review` in existing and future workflow definitions without changing workflow behavior.

**Architecture:** Preserve review state IDs and all transition contracts. Change the three default graph labels and make template reconciliation recognize either label. An Alembic data migration updates persisted review state display names for the three work-item object types, including the active workflow scheme.

**Tech Stack:** Python, SQLAlchemy, Alembic, FastAPI, pytest.

---

### Task 1: Lock the new template contract

**Files:**
- Modify: `backend/tests/test_default_workflow_review_subgraphs.py`
- Modify: `backend/tests/test_workflow_definition_api.py`

**Step 1: Write failing assertions**

For every default work-item graph, resolve the `pending_review` state and require `status_name == "Code Review"`. Update API graph assertions to require `Code Review` and reject the old label. Update the Git-triggered review test to expect `Code Review` after a requirement enters review.

**Step 2: Verify RED**

Run:

```powershell
Set-Location backend
& E:\miniforge3\python.exe -m pytest tests/test_default_workflow_review_subgraphs.py tests/test_git_triggered_work_item_review.py -q
```

Expected: assertions fail because default graphs still expose “待评审”.

### Task 2: Add the persisted-name migration test

**Files:**
- Create: `backend/tests/test_code_review_status_rename_migration.py`
- Create: `backend/alembic/versions/20260824_002_rename_review_states_to_code_review.py`

**Step 1: Write the failing migration test**

Require revision `20260824_002`, down revision `20260824_001`, and SQL constrained to `requirement`, `task`, and `bug` plus the exact old/new status names. Run the migration’s upgrade/downgrade against a temporary schema containing target and out-of-scope rows; assert only target work-item rows change.

**Step 2: Verify RED**

Run:

```powershell
Set-Location backend
& E:\miniforge3\python.exe -m pytest tests/test_code_review_status_rename_migration.py -q
```

Expected: fail because the migration does not exist.

### Task 3: Implement source and persisted-data rename

**Files:**
- Modify: `backend/app/services/default_workflow_template_service.py`
- Create: `backend/alembic/versions/20260824_002_rename_review_states_to_code_review.py`

**Step 1: Apply minimum source change**

Rename each `_state("pending_review", ...)` in requirement, task and Bug templates to `Code Review`. In `reconcile_review_subgraph()`, locate a review node with either name and rename an existing old node in place rather than adding another node.

**Step 2: Implement migration**

Use Alembic `op.execute()` to update only states whose definitions have target object types and whose existing name is “待评审”. Keep downgrade as a non-destructive no-op because a reverse rename could overwrite pre-existing custom `Code Review` states.

**Step 3: Verify GREEN**

Run the Task 1 and Task 2 commands. All focused tests must pass.

### Task 4: Verify runtime and local persisted scheme

**Files:**
- Verify only.

**Step 1: Upgrade local database and inspect head**

```powershell
Set-Location backend
& E:\miniforge3\python.exe -m alembic upgrade head
& E:\miniforge3\python.exe -m alembic heads
& E:\miniforge3\python.exe -m alembic current
```

Expected: one head/current revision, `20260824_002`.

**Step 2: Query active definitions**

Verify the active scheme’s requirement, task and Bug review nodes now read `Code Review`; their state IDs and review transition IDs remain unchanged.

**Step 3: Run adjacent regression suite**

```powershell
Set-Location backend
& E:\miniforge3\python.exe -m pytest tests/test_default_workflow_review_subgraphs.py tests/test_code_review_status_rename_migration.py tests/test_default_workflow_templates_api.py tests/test_workflow_definition_api.py tests/test_work_item_review_api.py tests/test_git_triggered_work_item_review.py -q
& E:\miniforge3\python.exe -m compileall -q app alembic/versions/20260824_002_rename_review_states_to_code_review.py
Set-Location ..
git diff --check
```

Expected: all selected tests, compilation and whitespace checks pass.

### Task 5: Restore the Git-triggered review regression fixture

**Files:**
- Modify: `backend/tests/test_git_triggered_work_item_review.py`

**Step 1: Replace the obsolete global-role fixture**

Use `ProjectMember.role_id` and `RoleCapability` to assign the developer and development-lead test users to the test project. The production review service already resolves reviewers from those project members.

**Step 2: Run the focused regression**

```powershell
Set-Location backend
& E:\miniforge3\python.exe -m pytest tests/test_git_triggered_work_item_review.py -q
```

Expected: the test collects successfully and asserts that Git-triggered review enters `Code Review`.
