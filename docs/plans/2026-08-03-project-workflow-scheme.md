# Project Workflow Scheme Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let workflow schemes define project lifecycle flows and initialize newly created projects from the selected scheme.

**Architecture:** Extend the scheme definition set from requirement/task/bug to requirement/task/bug/project. The project creation service will create its row, then resolve the selected scheme's project definition and initial state; projects without a scheme retain the system default. Existing projects will be removed before acceptance verification instead of migrating their in-flight status.

**Tech Stack:** Vue 3, Element Plus, FastAPI, SQLAlchemy, Alembic, pytest.

### Task 1: Define project as a scheme workflow type

**Files:**
- Modify: `backend/app/services/assignee_rule_config_service.py:180-260`
- Test: `backend/tests/test_assignee_rule_config_api.py`

**Step 1: Write the failing test**

Create a workflow scheme from the system template and assert it creates exactly one enabled `project` definition scoped to the scheme alongside the existing three definitions.

**Step 2: Run test to verify it fails**

Run: `E:\\miniforge3\\python.exe -m pytest tests/test_assignee_rule_config_api.py -q`

Expected: FAIL because the source and target definition lists omit `project`.

**Step 3: Write minimal implementation**

Include `project` in scheme definition creation, source lookup, graph copy, and scheme validity validation. Keep `iteration` system-scoped.

**Step 4: Run test to verify it passes**

Run: `E:\\miniforge3\\python.exe -m pytest tests/test_assignee_rule_config_api.py -q`

Expected: PASS.

### Task 2: Initialize new projects from their selected scheme

**Files:**
- Modify: `backend/app/services/workflow_state_service.py:14-66`
- Modify: `backend/app/services/project_service.py:237-257`
- Test: `backend/tests/test_program_project_api.py`

**Step 1: Write the failing test**

Create a scheme whose project graph has a distinct initial state, create a project with that scheme, then assert its `workflow_definition_id` and `current_state_id` match the scheme project definition. Add a control assertion that a project without a scheme uses the system project definition.

**Step 2: Run test to verify it fails**

Run: `E:\\miniforge3\\python.exe -m pytest tests/test_program_project_api.py -q`

Expected: FAIL because project creation currently calls `initial_system_workflow_values` unconditionally.

**Step 3: Write minimal implementation**

After the project row is flushed, resolve its effective `project` workflow using its selected scheme and assign the resolved definition and initial state before creating its requirement-pool iteration. Do not change the iteration initialization path.

**Step 4: Run test to verify it passes**

Run: `E:\\miniforge3\\python.exe -m pytest tests/test_program_project_api.py -q`

Expected: PASS.

### Task 3: Expose project in the scheme designer

**Files:**
- Modify: `frontend/src/components/WorkflowDesigner.vue:263-267`
- Modify: `frontend/src/views/WorkflowView.vue:6,74`
- Test: `frontend/src/components/workflowDesignerProjectType.test.mjs`

**Step 1: Write the failing test**

Assert the designer object-type options contain `{ label: '项目', value: 'project' }` and the workflow-page descriptions identify project lifecycle flow as configurable.

**Step 2: Run test to verify it fails**

Run: `npm test -- workflowdesignerprojecttype`

Expected: FAIL because the object type list stops at Bug.

**Step 3: Write minimal implementation**

Append the `project` object option and revise only the descriptive copy to list it.

**Step 4: Run test to verify it passes**

Run: `npm test -- workflowdesignerprojecttype`

Expected: PASS.

### Task 4: Clean existing project data and verify runtime behavior

**Files:**
- Verify only; no source change.

**Step 1: Apply required database migration**

Run: `E:\\miniforge3\\python.exe -m alembic upgrade head` from `backend`.

**Step 2: Delete existing projects and project-scoped data**

Use the project's existing project-deletion path or a reviewed database cleanup script. Verify the final project count is zero while users, programs, workflow definitions, and workflow schemes remain.

**Step 3: Create a new project under a scheme**

Create the project with an enabled workflow scheme, request `/workflow-runtime/project/{id}/transitions`, and verify the returned transition belongs to that scheme's project definition.

**Step 4: Run regression and build checks**

Run: `E:\\miniforge3\\python.exe -m pytest tests/test_assignee_rule_config_api.py tests/test_program_project_api.py -q`

Run: `npm test -- workflowdesignerprojecttype`

Run: `npm run build` from `frontend`.

Run: `git diff --check`.
