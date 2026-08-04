# Project Default Workflow Binding Implementation Plan

> **For Codex:** REQUIRED SKILL: Use `executing-plans` to implement this plan task-by-task.

**Goal:** Bind every newly created project to the default workflow scheme and require a workflow scheme selection in the project creation UI.

**Architecture:** The frontend selects the enabled default scheme when opening a create dialog and does not allow clearing it. The backend independently resolves an omitted scheme ID to the same default scheme before creating the project, so API callers receive the same persistent binding and its project workflow definition.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Node built-in assertions, pytest.

---

### Task 1: Default backend workflow scheme binding

**Files:**
- Modify: `backend/tests/test_program_project_api.py`
- Modify: `backend/app/services/assignee_rule_config_service.py`
- Modify: `backend/app/services/project_service.py`

**Step 1: Write the failing test**

Extend the unselected project creation coverage to assert that the returned project has the default scheme ID and the scheme's project workflow definition.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_program_project_api.py -k project_creation_uses_system_workflow_initial_state -q`

Expected: failure because `assignee_rule_config_id` is null.

**Step 3: Write minimal implementation**

Expose a default enabled workflow scheme resolver from the scheme service. In `resolve_project_create_payload`, set that scheme ID only when the request omits it; leave a supplied scheme untouched.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_program_project_api.py -k 'project_creation_uses_system_workflow_initial_state or project_creation_uses_selected_scheme_project_workflow' -q`

Expected: both default and manually selected scheme scenarios pass.

### Task 2: Default and required frontend selection

**Files:**
- Modify: `frontend/src/views/ProjectsView.vue`
- Create: `frontend/src/views/projectsDefaultWorkflowScheme.test.mjs`

**Step 1: Write the failing source-contract test**

Assert that the create form derives its initial scheme from the enabled default scheme and that the workflow scheme selector is not clearable.

**Step 2: Run test to verify it fails**

Run: `npm run test -- projectsDefaultWorkflowScheme`

Expected: failure because reset initializes the scheme to null and the selector is clearable.

**Step 3: Write minimal implementation**

Define the default scheme name once, select its enabled option during form reset, and remove the selector's `clearable` property.

**Step 4: Run test to verify it passes**

Run: `npm run test -- projectsDefaultWorkflowScheme`

Expected: the source contract passes.

### Task 3: Verify integration

**Files:**
- No production files expected beyond Tasks 1-2.

**Step 1: Run targeted backend and frontend tests**

Run: `pytest tests/test_program_project_api.py -k project_creation -q` and `npm run test -- workflow projectsDefaultWorkflowScheme`.

Expected: all selected tests pass.

**Step 2: Build the frontend**

Run: `npm run build`.

Expected: Vite completes successfully.

**Step 3: Inspect changes**

Run: `git diff --check` and `git status --short`.

Expected: only planned source, test, and plan files are changed.

**Delivery:** Do not commit, push, create a pull request, or merge without the user's explicit delivery choice.
