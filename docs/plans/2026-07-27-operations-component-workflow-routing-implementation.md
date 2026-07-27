# Operations Component Workflow Routing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Let a project register independent business components sourced from closed projects, then route requirements, tasks, and bugs through the selected primary component's members and workflow while retaining the project's shared iterations.

**Architecture:** Keep the existing project-to-workflow-scheme binding as the default. Add business components as project-scoped responsibility domains, with independently maintained members, an optional workflow-scheme override, and per-transition routing rules. Work items persist a primary-component association and continue to use their existing `workflow_definition_id` and `current_state_id`; switching an active item to another definition is only allowed through an audited, explicit state-mapping migration.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, pytest, Vue 3, Vite, Element Plus, Node test runner.

---

### Task 1: Lock the domain contract with API tests

**Files:**
- Create: `backend/tests/test_business_components_api.py`
- Modify: `backend/tests/test_workflow_runtime_api.py`
- Modify: `backend/tests/test_requirement_task_api.py`

**Step 1: Write failing component lifecycle tests**

Create a closed source project and an active target project. Assert that an authorized target-project manager can create a component from the source project, that its source ID/name snapshot is returned, and that creating from an active source project returns `409`.

```python
created = client.post(
    f"/api/v1/projects/{operations_project_id}/business-components/from-project",
    json={"source_project_id": closed_qa_project_id, "name": "QA档案管理"},
    headers=_auth(manager_token),
)
assert created.status_code == 201
assert created.json()["source_project_id"] == closed_qa_project_id
assert created.json()["source_project_name_snapshot"] == closed_qa_project_name
```

Add a test that a second enabled component in the same target project cannot use the same source project.

**Step 2: Write failing component-member isolation tests**

Seed different members in the closed source project and target operations project. Assert source members are returned as creation candidates, component members are copied only after explicit confirmation, and later component-member changes do not alter `project_members` for the source project.

**Step 3: Write failing work-item association tests**

Create a requirement, task, and bug in the operations project with a primary component. Assert each response includes `primary_component`, `related_components`, `source_project_id` derived from the primary component, and that a primary component from a different project is rejected.

**Step 4: Write failing runtime-routing and migration tests**

Cover all of the following:

- only an active member authorized by the primary component's transition route sees and executes that action;
- a project member who is not an authorized component member receives `403`;
- changing a component route changes the next eligible handler for an in-progress work item using the same definition;
- changing the component's workflow scheme affects a newly created requirement but not an existing requirement;
- migration without a valid old-state to new-state mapping returns `422` and leaves both IDs unchanged;
- a valid migration atomically changes both IDs and creates an audit/migration record.

**Step 5: Run the focused backend tests to verify they fail**

Run: `pytest backend/tests/test_business_components_api.py backend/tests/test_workflow_runtime_api.py backend/tests/test_requirement_task_api.py -v`

Expected: FAIL because business-component endpoints, models, component route resolution, and migration do not exist.

**Step 6: Commit the failing contract tests**

```bash
git add backend/tests/test_business_components_api.py backend/tests/test_workflow_runtime_api.py backend/tests/test_requirement_task_api.py
git commit -m "test: define component workflow routing contract"
```

### Task 2: Add persistent business-component and work-item association models

**Files:**
- Create: `backend/app/models/business_component.py`
- Modify: `backend/app/models/requirement.py`
- Modify: `backend/app/models/task.py`
- Modify: `backend/app/models/bug.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260727_001_business_component_workflow_routing.py`
- Modify: `backend/tests/test_model_metadata.py`

**Step 1: Add failing model metadata assertions**

Require these tables and columns in the model metadata test:

```text
business_components
business_component_members
business_component_transition_routes
work_item_components
workflow_migration_logs
```

Require foreign keys and indexes for component project/source-project lookup, component-member lookup, primary work-item lookup, and migration audit lookup.

**Step 2: Run the metadata test to verify it fails**

Run: `pytest backend/tests/test_model_metadata.py -v`

Expected: FAIL because the business-component tables are not registered.

**Step 3: Implement SQLAlchemy models and migration**

In `business_component.py`, add these models:

- `BusinessComponent`: target `project_id`, optional `source_project_id`, source-name snapshot, name, description, `owner_id`, optional `workflow_scheme_id`, enabled flag, timestamps.
- `BusinessComponentMember`: component ID, user ID, component role, enabled flag, effective interval, timestamps; unique per component/user.
- `BusinessComponentTransitionRoute`: component ID, work-item object type, transition ID, eligible-member mode, role/user settings, next-owner mode, fallback mode, enabled flag.
- `WorkItemComponent`: object type, object ID, component ID, relation type (`primary` or `related`), component-name snapshot; unique primary association per item and no duplicated component association.
- `WorkflowMigrationLog`: object type/ID, old and new definition/state IDs, reason, actor ID, timestamp.

The Alembic migration must create the tables, constraints, and indexes without touching existing project, iteration, or work-item rows. Register all models from `app.models.__init__` so metadata-based test setup creates them.

**Step 4: Run the metadata and migration tests**

Run: `pytest backend/tests/test_model_metadata.py backend/tests/test_workflow_state_migration.py -v`

Expected: PASS.

**Step 5: Commit the persistence layer**

```bash
git add backend/app/models backend/alembic/versions/20260727_001_business_component_workflow_routing.py backend/tests/test_model_metadata.py
git commit -m "feat: add business component persistence"
```

### Task 3: Implement component creation, independent membership, and component APIs

**Files:**
- Create: `backend/app/views/business_component_view.py`
- Create: `backend/app/services/business_component_service.py`
- Create: `backend/app/controllers/business_component_controller.py`
- Modify: `backend/app/controllers/router.py`
- Modify: `backend/app/services/project_permission_service.py`
- Modify: `backend/tests/test_business_components_api.py`

**Step 1: Define request and response views**

Add Pydantic views for component creation/update, creation from source project, member replacement, route replacement, workflow-scheme selection, work-item component associations, and migration requests. Read responses must include source-project metadata, owner name/ID, effective member list, route summaries, and usage counts.

**Step 2: Implement source-project creation as a snapshot**

`create_component_from_source_project` must:

1. validate that the target project is active and the source project is terminal;
2. reject duplicate enabled source-project associations in the target project;
3. snapshot the source project identity;
4. return proposed source members and source workflow scheme before any target membership change;
5. after explicit confirmation, add only confirmed users to the target project when permitted, then create independent component members;
6. clone the source workflow scheme into a component-owned scheme when one is present, rather than reusing a mutable source-project scheme.

Do not synchronize copied members or copied workflow definitions after creation.

**Step 3: Implement permissions and lifecycle endpoints**

Expose scoped routes under `/api/v1/projects/{project_id}/business-components`. Require the target project manager or a component manager for mutations, return `409` on changes to a terminal target project, and keep closed source projects read-only. Add a source-project read-only endpoint for reverse usage lookup.

**Step 4: Run focused component tests**

Run: `pytest backend/tests/test_business_components_api.py -v`

Expected: PASS, including source snapshot, explicit-copy, isolation, authorization, and duplicate-source coverage.

**Step 5: Commit the component API**

```bash
git add backend/app/views/business_component_view.py backend/app/services/business_component_service.py backend/app/controllers/business_component_controller.py backend/app/controllers/router.py backend/app/services/project_permission_service.py backend/tests/test_business_components_api.py
git commit -m "feat: manage project business components"
```

### Task 4: Resolve component workflows at work-item creation

**Files:**
- Modify: `backend/app/services/workflow_state_service.py`
- Modify: `backend/app/services/requirement_service.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/services/bug_service.py`
- Modify: `backend/app/views/requirement_view.py`
- Modify: `backend/app/views/task_view.py`
- Modify: `backend/app/views/bug_view.py`
- Modify: `backend/app/views/requirement_view.py`
- Modify: `backend/tests/test_business_components_api.py`
- Modify: `backend/tests/test_requirement_task_api.py`
- Modify: `backend/tests/test_bug_workflow_api.py`

**Step 1: Add failing workflow-precedence tests**

Assert the following exact precedence for a new work item:

```text
primary component workflow scheme
  > target project workflow scheme
  > existing system default workflow
```

Assert a related component cannot influence the selected definition. Assert a disabled component, a component outside the target project, and a component scheme not authorized for the project are rejected.

**Step 2: Extend `initial_workflow_values` minimally**

Add an optional `primary_component_id` argument. Resolve a component-owned scheme only after validating that the component is enabled and belongs to the supplied project; otherwise retain existing project and system fallback behavior. Return the existing two IDs only, so the rest of the runtime contract remains stable.

**Step 3: Persist component associations during creation and derivation**

Make requirement, task, and bug creation save one primary association and zero or more related associations in `work_item_components`. Derived tasks and bugs must inherit the requirement's primary/related component associations unless the caller explicitly supplies a valid override. Keep `project_id` equal to the operations project and set the existing `source_project_id` only as a denormalized read model from the primary component.

**Step 4: Expose associations in read models**

Add `primary_component` and `related_components` to requirement, task, and bug read payloads. Do not overload `source_project_id` as the writable association source.

**Step 5: Run creation and inheritance tests**

Run: `pytest backend/tests/test_business_components_api.py backend/tests/test_requirement_task_api.py backend/tests/test_bug_workflow_api.py -v`

Expected: PASS.

**Step 6: Commit the work-item integration**

```bash
git add backend/app/services/workflow_state_service.py backend/app/services/requirement_service.py backend/app/services/task_service.py backend/app/services/bug_service.py backend/app/views/requirement_view.py backend/app/views/task_view.py backend/app/views/bug_view.py backend/tests/test_business_components_api.py backend/tests/test_requirement_task_api.py backend/tests/test_bug_workflow_api.py
git commit -m "feat: bind work items to component workflows"
```

### Task 5: Add component-aware transition authorization and handler routing

**Files:**
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/views/workflow_runtime_view.py`
- Modify: `backend/app/services/business_component_service.py`
- Modify: `backend/tests/test_workflow_runtime_api.py`
- Modify: `backend/tests/test_business_components_api.py`

**Step 1: Add failing runtime tests for component-only candidates**

For a requirement with a primary component, assert `GET /workflow-runtime/.../transitions` only returns component-authorized actions. Assert `eligible_assignee_ids` contains only active primary-component members allowed by that action, even when the project has additional members.

**Step 2: Add a pure component route resolver**

Implement helpers in `business_component_service.py` that accept a work item, transition, and target project and return:

- whether the component route restricts the action;
- eligible executor IDs;
- eligible manual-next-owner IDs;
- an automatically resolved next owner;
- the configured fallback behavior.

Resolve user IDs and component roles from active component members only. Keep the existing project-member resolver as the fallback when the item has no primary component or the component has no enabled route for that action.

**Step 3: Integrate the resolver at every runtime decision point**

Update `list_available_transitions`, `execute_transition`, `_eligible_manual_assignee_ids`, `_next_owner_resolution`, and `owner_has_executable_current_action` to use the component resolver before project-role rules. Do not let a previously assigned but now-inactive component member execute a component-restricted action.

**Step 4: Handle member removal safely**

When an active component member is removed, validate impacted non-terminal items. Require an explicit transfer to another eligible component member or move the item to the configured component pending-assignment fallback; preserve all historical operation records.

**Step 5: Run runtime regression tests**

Run: `pytest backend/tests/test_workflow_runtime_api.py backend/tests/test_business_components_api.py backend/tests/test_requirement_task_api.py -v`

Expected: PASS.

**Step 6: Commit runtime routing**

```bash
git add backend/app/services/workflow_runtime_service.py backend/app/views/workflow_runtime_view.py backend/app/services/business_component_service.py backend/tests/test_workflow_runtime_api.py backend/tests/test_business_components_api.py backend/tests/test_requirement_task_api.py
git commit -m "feat: route workflow actions through component members"
```

### Task 6: Implement explicit work-item workflow migration

**Files:**
- Modify: `backend/app/services/business_component_service.py`
- Modify: `backend/app/controllers/business_component_controller.py`
- Modify: `backend/app/views/business_component_view.py`
- Modify: `backend/tests/test_business_components_api.py`
- Modify: `backend/tests/test_workflow_runtime_api.py`

**Step 1: Add failing migration safety tests**

Create an in-progress item in workflow definition A, then change the component's default scheme to definition B. Verify that A remains on the item. Test a missing target state, a target state belonging to the wrong definition, an unauthorized actor, and a valid `A.current_state_id -> B.target_state_id` migration.

**Step 2: Implement a transactional migration service**

Add `migrate_work_item_workflow` that locks the item, validates non-terminal state, validates the component and new definition, verifies the target state belongs to the new definition, updates `workflow_definition_id` and `current_state_id` together, validates the resulting next-owner route, and creates `WorkflowMigrationLog` plus an audit entry.

**Step 3: Expose migration only as an explicit action**

Add a component-scoped endpoint such as `POST /business-components/{component_id}/work-items/{object_type}/{object_id}/workflow-migrations`. It requires a reason and only permits the component owner, target-project manager, or system administrator. Do not expose migration through ordinary work-item PATCH.

**Step 4: Run migration tests**

Run: `pytest backend/tests/test_business_components_api.py backend/tests/test_workflow_runtime_api.py -v`

Expected: PASS.

**Step 5: Commit workflow migration**

```bash
git add backend/app/services/business_component_service.py backend/app/controllers/business_component_controller.py backend/app/views/business_component_view.py backend/tests/test_business_components_api.py backend/tests/test_workflow_runtime_api.py
git commit -m "feat: migrate component work item workflows explicitly"
```

### Task 7: Add component APIs and management UI

**Files:**
- Create: `frontend/src/api/businessComponents.js`
- Create: `frontend/src/views/ProjectComponentsView.vue`
- Create: `frontend/src/views/projectComponentsView.test.mjs`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/api/projects.js`

**Step 1: Write failing component-view behavior tests**

Use source-level Vue behavior tests to assert the view loads components for the route project, exposes the source-project creation action, has sections for members/workflow/routes, hides mutations for closed projects, and uses the new API module rather than inline HTTP calls.

**Step 2: Implement the API module and project-scoped route**

Add typed-style API functions for component CRUD, source-project preview/create, member replacement, route replacement, usage queries, and workflow migration. Add a nested project route to the router and a “业务组件” entry from project detail.

**Step 3: Build the component management surface**

Implement a dense project-scoped page with:

- component list showing source project, status, owner, member count, workflow scheme, and open-item count;
- source-project creation wizard with previewed member/workflow copy and explicit confirmation;
- component detail drawer or route with base information, independent member roster, selected workflow scheme, per-action routing, associated work items, and audit history;
- read-only state for terminal projects.

Use existing Element Plus controls and project permission helpers. Do not reuse the workflow-designer component registry UI.

**Step 4: Run the focused frontend test**

Run: `npm test -- projectComponentsView`

Working directory: `frontend`

Expected: PASS.

**Step 5: Commit the component UI**

```bash
git add frontend/src/api/businessComponents.js frontend/src/views/ProjectComponentsView.vue frontend/src/views/projectComponentsView.test.mjs frontend/src/router/index.js frontend/src/views/ProjectDetailView.vue frontend/src/api/projects.js
git commit -m "feat: manage project business components in the UI"
```

### Task 8: Add primary and related component selection to work-item flows

**Files:**
- Modify: `frontend/src/components/work-items/RequirementEditDialog.vue`
- Modify: `frontend/src/components/work-items/TaskEditDialog.vue`
- Modify: `frontend/src/components/work-items/BugEditDialog.vue`
- Modify: `frontend/src/views/RequirementsView.vue`
- Modify: `frontend/src/views/TasksView.vue`
- Modify: `frontend/src/views/BugsView.vue`
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Create: `frontend/src/utils/workItemComponents.js`
- Create: `frontend/src/utils/workItemComponents.test.mjs`

**Step 1: Write failing pure-helper tests**

Test that a primary component is required only when the selected project has active components, that related components exclude the primary component, that all selected components belong to the selected project, and that switching project clears invalid component selections.

**Step 2: Implement component selection helpers**

Add pure functions that normalize API component payloads, return eligible components for a project, reject disabled components, and derive the source-project display from the primary component.

**Step 3: Update create and edit dialogs**

Load components when the project changes. Add one required “主组件” select for projects with active components and a multiple “关联组件” select. Send `primary_component_id` and `related_component_ids` in create/update payloads. On edit, prohibit changing the primary component after the item has left its initial state; direct users to the explicit workflow/component transfer flow instead.

**Step 4: Update lists and project detail**

Show the primary component and source project in requirements, tasks, bugs, and project-detail tables. Add filters for primary and related components. Keep iteration selection scoped only by the owning operations project, not by component.

**Step 5: Run focused frontend tests**

Run: `npm test -- workItemComponents`

Working directory: `frontend`

Expected: PASS.

**Step 6: Commit work-item component selection**

```bash
git add frontend/src/components/work-items frontend/src/views/RequirementsView.vue frontend/src/views/TasksView.vue frontend/src/views/BugsView.vue frontend/src/views/ProjectDetailView.vue frontend/src/utils/workItemComponents.js frontend/src/utils/workItemComponents.test.mjs
git commit -m "feat: select components on operational work items"
```

### Task 9: Expose component-aware runtime controls and migration UI

**Files:**
- Modify: `frontend/src/components/WorkflowActionButtons.vue`
- Modify: `frontend/src/api/workflowRuntime.js`
- Modify: `frontend/src/views/RequirementDetailView.vue`
- Modify: `frontend/src/views/TaskDetailView.vue`
- Modify: `frontend/src/views/BugDetailView.vue`
- Create: `frontend/src/components/workflowActionButtonsComponentRoute.test.mjs`

**Step 1: Write failing action-button tests**

Assert that manual-next-owner controls use the component-filtered `eligible_assignee_ids` returned by the runtime, show the current primary component context, and do not offer an unauthorized action.

**Step 2: Implement component-aware action presentation**

Use the existing runtime response as the authority. Add the primary component label and source-project context in detail views. Preserve existing project-only behavior when the item has no primary component.

**Step 3: Add the explicit migration command in detail views**

For authorized users only, provide a guarded action that loads target states from the selected component scheme, requires a migration reason, calls the migration endpoint, and reloads the work item. Do not place it in the ordinary edit form.

**Step 4: Run frontend action tests and build**

Run: `npm test -- workflowActionButtonsComponentRoute`

Run: `npm run build`

Working directory: `frontend`

Expected: both commands exit `0`.

**Step 5: Commit runtime UI integration**

```bash
git add frontend/src/components/WorkflowActionButtons.vue frontend/src/api/workflowRuntime.js frontend/src/views/RequirementDetailView.vue frontend/src/views/TaskDetailView.vue frontend/src/views/BugDetailView.vue frontend/src/components/workflowActionButtonsComponentRoute.test.mjs
git commit -m "feat: show component workflow routing controls"
```

### Task 10: Run regression, migration, and build verification

**Files:**
- Modify: `docs/prd/2026-07-25-project-completion-and-operations-components-prd.md` only if an implemented behavior differs from an approved rule
- Create: `docs/reports/2026-07-27-operations-component-workflow-routing-report.md`

**Step 1: Run the complete backend suite**

Run: `pytest backend/tests -v`

Expected: all tests pass, including migration and existing project-workflow regressions.

**Step 2: Run frontend tests and production build**

Run: `npm test`

Run: `npm run build`

Working directory: `frontend`

Expected: both exit `0`.

**Step 3: Validate migration upgrade and downgrade in an isolated database**

Run the repository's established Alembic migration test path for the new revision. Confirm fresh schema creation, upgrade, downgrade, and re-upgrade all preserve the required component constraints.

**Step 4: Write the completion report**

Record test commands, results, implemented endpoints, data migrations, known deferrals, and the confirmed behavior that source projects remain immutable while component routing is live for in-progress items using the same workflow definition.

**Step 5: Commit verification artifacts**

```bash
git add docs/prd/2026-07-25-project-completion-and-operations-components-prd.md docs/reports/2026-07-27-operations-component-workflow-routing-report.md
git commit -m "docs: report component workflow routing delivery"
```
