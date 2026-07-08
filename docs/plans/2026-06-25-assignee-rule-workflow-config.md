# Assignee Rule Workflow Config Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current exposed workflow configuration UI with reusable default assignee rule configurations that projects can bind to.

**Architecture:** Add an `assignee_rule_configs` table storing reusable role rules for requirements, tasks, test cases, test runs, and bugs. Projects bind to one config through a new `assignee_rule_config_id` field. Backend default assignee resolution reads the bound config first, then falls back to current hardcoded role defaults.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pytest, Vue 3, Element Plus, Vite.

---

### Task 1: Backend Model And Migration

**Files:**
- Create: `backend/app/models/assignee_rule_config.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/project.py`
- Create: `backend/alembic/versions/20260625_002_assignee_rule_configs.py`

**Steps:**
1. Add model fields: `id`, `name`, `description`, `requirement_owner_roles`, `task_owner_roles`, `test_case_tester_roles`, `test_run_owner_roles`, `bug_owner_roles`, `enabled`, timestamps.
2. Add `projects.assignee_rule_config_id`.
3. Seed one default config in migration matching current behavior:
   - requirement: `developer,tech_lead,development_lead,product_owner,product_manager`
   - task: `developer,tech_lead,development_lead`
   - test case: `tester,test_lead`
   - test run: `tester,test_lead`
   - bug: `developer,tech_lead,development_lead`
4. Verify migration imports compile.

### Task 2: Backend API

**Files:**
- Create: `backend/app/views/assignee_rule_config_view.py`
- Create: `backend/app/services/assignee_rule_config_service.py`
- Create: `backend/app/controllers/assignee_rule_config_controller.py`
- Modify: `backend/app/controllers/router.py`
- Test: `backend/tests/test_assignee_rule_config_api.py`

**Steps:**
1. Write tests for list, create, update, disable/delete behavior.
2. Implement CRUD endpoints under `/api/v1/assignee-rule-configs`.
3. Keep delete as soft-disable to avoid breaking projects using a config.
4. Return enabled configs ordered by `id`.

### Task 3: Project Binding

**Files:**
- Modify: `backend/app/views/project_view.py`
- Modify: `backend/app/services/project_service.py`
- Modify: `frontend/src/api/projects.js`
- Test: `backend/tests/test_program_project_api.py`

**Steps:**
1. Add `assignee_rule_config_id` to project create/update/read schemas.
2. Persist the field on project create/update.
3. Keep existing `workflow_config_id` untouched for compatibility.
4. Add a project API test that sets and reads `assignee_rule_config_id`.

### Task 4: Default Assignee Resolution

**Files:**
- Modify: `backend/app/services/project_team_service.py`
- Test: `backend/tests/test_program_project_api.py`

**Steps:**
1. Add role-list based resolver that reads project bound config.
2. Update default functions:
   - `default_requirement_owner_id`
   - `default_developer_id` for task/bug callers
   - `default_tester_id`
   - add `default_test_run_owner_id` if test runs use it.
3. Preserve current fallback role behavior when no config or no matching member.
4. Add tests proving a custom config can make requirement owner default to tester or product role based on project team roles.

### Task 5: Frontend Workflow Config Replacement

**Files:**
- Modify: `frontend/src/views/WorkflowView.vue`
- Create: `frontend/src/api/assigneeRuleConfigs.js`

**Steps:**
1. Keep left navigation text as `工作流配置`.
2. Replace canvas UI with a rules config list and editor.
3. Allow selecting roles for each object type using project member role labels.
4. Support create/update/disable.
5. Do not expose the old workflow canvas UI from the main route.

### Task 6: Project UI Binding

**Files:**
- Modify: `frontend/src/views/ProjectsView.vue`
- Modify: `frontend/src/views/ProjectDetailView.vue`

**Steps:**
1. Load assignee rule configs.
2. Add selector labeled `工作流配置` or `责任人规则配置` in project create/edit forms.
3. Save `assignee_rule_config_id`.
4. In project detail, show/edit the bound config consistently.

### Task 7: Verification

**Commands:**
- `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests/test_assignee_rule_config_api.py backend/tests/test_program_project_api.py backend/tests/test_requirement_task_api.py -q`
- `npm --prefix frontend run build`

**Expected:** Backend tests pass; frontend build succeeds with only existing Rollup/chunk warnings.
