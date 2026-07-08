# Project Permission Boundary Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the PRD-defined project permission boundary for project management, assignment, and workflow transition operations.

**Architecture:** Add a centralized backend project permission service and route existing permission checks through it. Keep the first version scoped to backend enforcement for high-risk operations: project configuration/member management, work item assignment, dynamic workflow transitions, and work item edits.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue/Vite build verification.

---

### Task 1: Permission Service

**Files:**
- Create: `backend/app/services/project_permission_service.py`
- Modify: `backend/app/services/current_handler_service.py`
- Test: `backend/tests/test_project_permission_boundary_api.py`

**Steps:**
1. Write failing tests for project member vs project owner vs system admin permissions.
2. Add permission helpers for system admin, project owner, project member, current handler, project management, assignment, deletion, and admin action.
3. Rewire `current_handler_service.ensure_assign_permission` and workflow runtime delegation to the new service.
4. Run permission tests.

### Task 2: Project Endpoints

**Files:**
- Modify: `backend/app/controllers/project_controller.py`
- Modify: `backend/app/services/project_service.py`
- Test: `backend/tests/test_project_permission_boundary_api.py`

**Steps:**
1. Add tests proving ordinary project members cannot update project info, manage members, or delete projects.
2. Allow project owner to update project info and manage members.
3. Restrict project delete to system admin.
4. Run permission tests.

### Task 3: Work Item Edit And Assignment

**Files:**
- Modify: `backend/app/services/requirement_service.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/services/bug_service.py`
- Modify: `backend/app/services/assignment_service.py`
- Test: `backend/tests/test_project_permission_boundary_api.py`

**Steps:**
1. Add tests proving non-current-handler members cannot edit work items.
2. Allow current handler, project owner, and system admin to edit.
3. Keep project owner and system admin allowed to assign and batch assign.
4. Run permission tests.

### Task 4: Verification

**Commands:**
- `E:\miniforge3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_project_permission_boundary_api.py backend\tests\test_workflow_runtime_api.py backend\tests\test_current_handler_assignment_api.py backend\tests\test_unassigned_work_items_api.py -q`
- `npm run build`

**Expected:** All selected backend tests and frontend build pass.
