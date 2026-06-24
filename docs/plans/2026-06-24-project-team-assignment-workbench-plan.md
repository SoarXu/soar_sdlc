# Project Team Assignment And Workbench Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace project-owner based default assignment with project-team roles, and make workbench and Code Review follow organization responsibilities.

**Architecture:** Keep system roles for broad identity, and add project team roles for execution responsibility inside each project. Backend services resolve default assignees through project_members before falling back to legacy owner_id, while the workbench filters by the user's managed or participated project scope.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, MySQL, Vue 3, Element Plus.

---

### Task 1: Project Team Data Model

**Files:**
- Create: `backend/alembic/versions/20260624_003_project_team_roles.py`
- Modify: `backend/app/models/project_member.py`
- Modify: `backend/app/views/project_view.py`
- Modify: `backend/app/controllers/project_controller.py`
- Modify: `backend/app/services/project_service.py`

**Steps:**
1. Add `is_default_assignee`, `is_workbench_participant`, and `sort_order` to `project_members`.
2. Expose `GET /api/v1/projects/{project_id}/members` and `PUT /api/v1/projects/{project_id}/members`.
3. Preserve existing member rows and allow role values including `product_owner`, `tech_lead`, `developer`, `test_lead`, `tester`, and `viewer`.

### Task 2: Default Assignee Rules

**Files:**
- Create: `backend/app/services/project_team_service.py`
- Modify: `backend/app/services/requirement_service.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/services/bug_service.py`
- Modify: `backend/app/services/test_case_service.py`

**Steps:**
1. Resolve requirement owner from project default product owner.
2. Resolve standalone task owner from project default developer or tech lead.
3. Resolve test case tester from project default tester or test lead.
4. Resolve bug owner from task owner, then project default developer or tech lead, then requirement owner.

### Task 3: Workbench Scope

**Files:**
- Modify: `backend/app/services/dashboard_service.py`

**Steps:**
1. For lead/product/test roles, include active iterations only from projects where the user is a project team participant or responsible program/project owner.
2. For developer, keep personal work-item filtering.
3. Keep administrators on all-work scope.

### Task 4: Code Review Reviewer Selection

**Files:**
- Modify: `backend/app/services/devops_service.py`

**Steps:**
1. Match commit author to user by email, full name, or username.
2. Choose reviewer from project tech lead/development lead first, excluding the author.
3. Fall back to another global development lead, then system administrator or program owner.
4. Never assign the review task to the commit author when another reviewer exists.

### Task 5: Frontend Project Members

**Files:**
- Modify: `frontend/src/api/projects.js`
- Modify: `frontend/src/views/ProjectDetailView.vue`

**Steps:**
1. Load and save project members in the project detail Members tab.
2. Add role, default assignee, and workbench participant controls.
3. Use project team defaults when opening requirement, task, case, and bug create dialogs.

### Task 6: Verification

**Commands:**
- `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests/test_program_project_api.py::test_project_members_drive_default_assignees backend/tests/test_dashboard_workbench_api.py::test_development_lead_workbench_is_limited_to_project_team_scope backend/tests/test_devops_code_review_api.py::test_development_lead_commit_is_assigned_to_another_reviewer -q`
- `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests/test_program_project_api.py backend/tests/test_dashboard_workbench_api.py backend/tests/test_devops_code_review_api.py -q`
- `npm run build` from `frontend`
- `git diff --check`
