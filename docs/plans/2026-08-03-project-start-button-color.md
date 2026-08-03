# Project Start Button Color Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Render project workflow action `start` as the same green success action used for program launch.

**Architecture:** The runtime API exposes the button type from each transition's `ui_config`. The project default workflow will explicitly set `button_type: "success"`, and a new Alembic migration will add that setting to every persisted project `start` transition while retaining its existing configuration.

**Tech Stack:** Python, Alembic, SQLAlchemy, pytest.

### Task 1: Cover persisted project start-button configuration

**Files:**
- Modify: `backend/tests/test_project_start_button_migration.py`
- Test: `backend/tests/test_project_start_button_migration.py`

**Step 1: Write the failing test**

Add a test that imports the new migration helper with a project start transition whose `ui_config` does not contain `button_type`, then assert the returned configuration retains `list_display` and adds `button_type: "success"`.

**Step 2: Run test to verify it fails**

Run: `E:\\miniforge3\\python.exe -m pytest tests/test_project_start_button_migration.py -q`

Expected: FAIL because the new migration helper does not yet exist.

### Task 2: Migrate existing transitions

**Files:**
- Create: `backend/alembic/versions/20260803_001_set_project_start_button_success.py`
- Modify: `backend/tests/test_project_start_button_migration.py`

**Step 1: Write minimal implementation**

Create revision `20260803_001` after `20260731_001`. Select project `start` transitions, parse each `ui_config`, set only `button_type` to `success`, and update the serialized configuration.

**Step 2: Run test to verify it passes**

Run: `E:\\miniforge3\\python.exe -m pytest tests/test_project_start_button_migration.py -q`

Expected: PASS.

### Task 3: Configure future projects

**Files:**
- Modify: `backend/app/services/default_workflow_template_service.py`
- Modify: `backend/tests/test_project_start_button_migration.py`
- Test: `backend/tests/test_project_start_button_migration.py`

**Step 1: Write the failing test**

Assert the default project `start` transition has `ui_config["button_type"] == "success"`.

**Step 2: Write minimal implementation**

Add `button_type: "success"` to the project `start` transition's existing `ui_config` without changing its list placement or priority.

**Step 3: Run test to verify it passes**

Run: `E:\\miniforge3\\python.exe -m pytest tests/test_project_start_button_migration.py -q`

Expected: PASS.

### Task 4: Verify the deployed state

**Files:**
- Verify only.

**Step 1: Apply migration**

Run: `E:\\miniforge3\\python.exe -m alembic upgrade head`

**Step 2: Verify database and regression suite**

Run: `E:\\miniforge3\\python.exe -m alembic current`

Run: `E:\\miniforge3\\python.exe -m pytest tests/test_project_start_button_migration.py tests/test_project_start_action_label_migration.py -q`

Expected: database at `20260803_001 (head)` and all tests pass.

**Step 3: Verify frontend build**

Run: `npm run build` from `frontend`.

**Step 4: Inspect whitespace**

Run: `git diff --check`
