# Ownerless Workbench Handler Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the default owner concept from workflow setup and object creation while keeping current handler assignment as the workbench routing mechanism.

**Architecture:** Keep existing `owner_id` database fields as the technical current-handler storage. Stop auto-populating those fields from default role settings on create/import flows, and hide the obsolete default role controls from the workflow page.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3, Element Plus, Vite.

---

### Task 1: Backend Creation Defaults

**Files:**
- Modify: `backend/tests/test_current_handler_assignment_api.py`
- Modify: `backend/tests/test_requirement_import_api.py`
- Modify: `backend/app/services/requirement_service.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/services/bug_service.py`
- Modify: `backend/app/services/test_case_service.py`
- Modify: `backend/app/services/requirement_import_service.py`

**Steps:**
1. Add/update failing tests proving requirements, tasks, bugs, test-run bugs, and requirement imports remain unassigned when no current handler is explicitly supplied.
2. Run the targeted pytest command and confirm the old auto-owner behavior fails these tests.
3. Remove default owner assignment from create/import paths.
4. Run the targeted pytest command again.

### Task 2: Frontend Workflow Configuration

**Files:**
- Modify: `frontend/src/views/WorkflowView.vue`
- Modify: `frontend/src/views/DashboardView.vue`

**Steps:**
1. Remove default owner role controls and stale introductory copy from workflow configuration.
2. Keep compatibility payload fields as empty strings until the backend schema is migrated.
3. Remove "负责人" wording from workbench-facing text; use "当前处理人" or "待分派".
4. Build the frontend with `npm run build`.

### Task 3: Verification

**Commands:**
- `E:\miniforge3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_current_handler_assignment_api.py backend\tests\test_requirement_import_api.py backend\tests\test_unassigned_work_items_api.py backend\tests\test_workflow_definition_api.py -q`
- `npm run build`

