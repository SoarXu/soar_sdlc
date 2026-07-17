# Workflow ID Finalization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the remaining workflow state-string identity from projects, iterations, states, and transitions while keeping `action_key` and making transition-local `handler_rule` the only assignee-routing configuration.

**Architecture:** Add and backfill project/iteration workflow definition and current-state foreign keys before switching all runtime consumers to ID relationships. Refactor system-template creation to use request-local references only, remove automatic status-key reconciliation, then audit and drop the legacy columns and duplicate handler-rule table in a final destructive migration.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, MySQL 8, Pydantic 2, Vue 3, Element Plus, pytest, Node test scripts, Vite.

---

## Delivery Rules

- Work in an isolated worktree created from the approved design commit.
- Preserve unrelated uncommitted changes in the main checkout.
- Use the isolated database `intellective_bio_sdlc_workflow_state_model_test`.
- Follow red-green-refactor for every task and commit only after focused tests pass.
- Keep `programs.status` and `workflow_transitions.action_key` unchanged.
- Do not introduce `template_ref`, a replacement status code, or template versioning.

### Task 1: Add Project And Iteration State Identity

**Files:**
- Create: `backend/alembic/versions/20260717_001_project_iteration_state_identity.py`
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/models/iteration.py`
- Modify: `backend/app/views/project_view.py`
- Modify: `backend/app/views/iteration_view.py`
- Modify: `backend/app/services/workflow_state_service.py`
- Modify: `backend/tests/test_model_metadata.py`
- Create: `backend/tests/test_project_iteration_state_migration.py`

- [ ] **Step 1: Write failing metadata tests**

Assert `Project` and `Iteration` expose transitional nullable ID fields and that their read schemas expose the ID fields plus `status_name`. Legacy `status` remains temporarily available until Task 6:

```python
for model in (Project, Iteration):
    assert "workflow_definition_id" in model.__table__.c
    assert "current_state_id" in model.__table__.c
    assert model.__table__.c.workflow_definition_id.nullable is True
    assert model.__table__.c.current_state_id.nullable is True
```

- [ ] **Step 2: Write migration fixture tests**

Create legacy project/iteration rows for every canonical status. Upgrade through `20260717_001` and assert each row receives the system definition for its object type and the state whose pre-migration `status_key` matched the old status. Add fixtures for an unknown status, a missing system definition, and an ambiguous matching state; each must fail with the affected object IDs in the error.

- [ ] **Step 3: Run focused tests and confirm RED**

Run:

```powershell
python -m pytest tests/test_model_metadata.py tests/test_project_iteration_state_migration.py -q
```

Expected: missing model columns and missing migration revision failures.

- [ ] **Step 4: Implement the additive migration and transitional models**

The migration must:

```python
op.add_column("projects", sa.Column("workflow_definition_id", bigint, nullable=True))
op.add_column("projects", sa.Column("current_state_id", bigint, nullable=True))
op.add_column("iterations", sa.Column("workflow_definition_id", bigint, nullable=True))
op.add_column("iterations", sa.Column("current_state_id", bigint, nullable=True))
```

Resolve exactly one enabled system definition per object type and map each old status through the existing `workflow_states.status_key`. Backfill before adding indexes and foreign keys. Abort with a deterministic diagnostic if any active or deleted row cannot be mapped without guessing.

Add SQLAlchemy foreign-key columns and a shared helper:

```python
def initial_system_workflow_values(db: Session, object_type: str) -> tuple[int, int]:
    """Return the enabled system definition and its enabled initial-state ID."""
```

- [ ] **Step 5: Run focused tests and confirm GREEN**

Run the command from Step 3 and require zero failures.

- [ ] **Step 6: Commit**

```powershell
git add backend/alembic/versions/20260717_001_project_iteration_state_identity.py backend/app/models/project.py backend/app/models/iteration.py backend/app/views/project_view.py backend/app/views/iteration_view.py backend/app/services/workflow_state_service.py backend/tests/test_model_metadata.py backend/tests/test_project_iteration_state_migration.py
git commit -m "feat: add project and iteration state identity"
```

### Task 2: Make System Template Persistence ID-Only

**Files:**
- Modify: `backend/app/views/workflow_definition_view.py`
- Modify: `backend/app/services/default_workflow_template_service.py`
- Modify: `backend/app/services/workflow_definition_service.py`
- Modify: `backend/tests/test_default_workflow_templates_api.py`
- Modify: `backend/tests/test_workflow_definition_api.py`

- [ ] **Step 1: Write failing template tests**

Prove that calling template initialization twice preserves every definition, state, transition, and initial-state ID. Prove fresh initialization builds all five system definitions without persisting a state code. Prove an existing state renamed through the graph API remains renamed after another initialization call.

```python
first = snapshot_system_graph_ids(client)
rename_state_by_id(client, first.project_state_id, "项目进行中（调整）")
client.get("/api/v1/workflow-definitions?scope_type=system")
assert snapshot_system_graph_ids(client) == first
assert read_state(first.project_state_id).status_name == "项目进行中（调整）"
```

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m pytest tests/test_default_workflow_templates_api.py tests/test_workflow_definition_api.py -q
```

Expected: current reconciliation still reads and rewrites `status_key`.

- [ ] **Step 3: Replace persisted template codes with request-local references**

Change template-only Pydantic fields to `ref`, `from_ref`, and `to_ref`. These values may exist in Python template declarations but must never be ORM columns or public graph fields. Initialization behavior becomes:

```python
definition = find_system_definition(template_key)
if definition:
    return definition
states_by_ref = create_states_and_flush(template.states)
create_transitions_with_ids(template.transitions, states_by_ref)
definition.initial_state_id = states_by_ref[template.initial_ref].id
```

Remove update-in-place reconciliation from `ensure_default_workflow_templates`. Existing graphs are read and saved only by numeric IDs.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run the command from Step 2 and require zero failures.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/views/workflow_definition_view.py backend/app/services/default_workflow_template_service.py backend/app/services/workflow_definition_service.py backend/tests/test_default_workflow_templates_api.py backend/tests/test_workflow_definition_api.py
git commit -m "refactor: persist system templates by state id"
```

### Task 3: Migrate Project And Iteration Runtime

**Files:**
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/services/project_service.py`
- Modify: `backend/app/services/iteration_service.py`
- Modify: `backend/app/services/status_operation_service.py`
- Modify: `backend/app/services/workflow_state_query_service.py`
- Modify: `backend/app/controllers/project_controller.py`
- Modify: `backend/app/controllers/iteration_controller.py`
- Modify: `backend/tests/test_program_project_api.py`
- Modify: `backend/tests/test_iteration_detail_api.py`
- Modify: `backend/tests/test_workflow_runtime_api.py`

- [ ] **Step 1: Write failing runtime tests**

Cover these behaviors:

- New projects and iterations use the relevant system definition and its `initial_state_id`.
- Available actions query `WorkflowTransition.from_state_id` for all five workflow object types.
- Executing a project or iteration action updates only `current_state_id`, never a string status.
- Direct start/pause/resume/close endpoints delegate to the configured action and produce the same result as the generic runtime endpoint.
- Status-name changes do not alter project/iteration gate outcomes or action discovery.
- Cross-definition current-state corruption returns a diagnostic and never falls back to a status string.

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m pytest tests/test_program_project_api.py tests/test_iteration_detail_api.py tests/test_workflow_runtime_api.py -q
```

- [ ] **Step 3: Generalize ID runtime to project and iteration**

Replace `CORE_ID_OBJECT_TYPES` branching with a single ID-based path for requirement, task, bug, project, and iteration. Definition resolution for an existing item starts from `item.workflow_definition_id`; current-state resolution requires `item.current_state_id` in that definition.

All action lookup uses:

```python
WorkflowTransition.definition_id == item.workflow_definition_id
WorkflowTransition.from_state_id == item.current_state_id
WorkflowTransition.action_key == requested_action_key
```

Project/iteration domain validators must inspect the current or target state category and configured validator type, not compare names. Operation history receives definition/state IDs and state-name snapshots.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run the command from Step 2 and require zero failures.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/workflow_runtime_service.py backend/app/services/project_service.py backend/app/services/iteration_service.py backend/app/services/status_operation_service.py backend/app/services/workflow_state_query_service.py backend/app/controllers/project_controller.py backend/app/controllers/iteration_controller.py backend/tests/test_program_project_api.py backend/tests/test_iteration_detail_api.py backend/tests/test_workflow_runtime_api.py
git commit -m "feat: run project and iteration workflows by state id"
```

### Task 4: Remove Duplicate Handler Transition Rules

**Files:**
- Delete: `backend/app/models/handler_transition_rule.py`
- Delete: `backend/app/views/handler_transition_rule_view.py`
- Delete: `backend/app/services/handler_transition_rule_service.py`
- Delete: `backend/app/controllers/handler_transition_rule_controller.py`
- Delete: `frontend/src/api/handlerTransitionRules.js`
- Modify: `backend/app/controllers/router.py`
- Modify: `backend/app/services/workflow_definition_service.py`
- Modify: `backend/app/services/assignee_rule_config_service.py`
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_model_metadata.py`
- Delete: `backend/tests/test_handler_transition_cleanup_api.py`
- Modify: `backend/tests/test_workflow_definition_api.py`
- Modify: `backend/tests/test_assignee_rule_config_api.py`

- [ ] **Step 1: Write failing single-source tests**

Assert graph save, graph read, scheme copy, and runtime owner routing preserve and use `transition.handler_rule` without creating or querying `handler_transition_rules`. Add a repository source guard that rejects imports, routes, table names, and old frontend API paths.

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m pytest tests/test_workflow_definition_api.py tests/test_assignee_rule_config_api.py tests/test_model_metadata.py -q
```

- [ ] **Step 3: Remove synchronization and old components**

Delete `_sync_handler_rules` and `_clone_additional_handler_rules`. Scheme copying already deep-copies `WorkflowTransition.handler_rule`; keep that as the sole copy path. Remove the old router registration, backend CRUD surface, model, test cleanup list entry, and unused frontend API module.

- [ ] **Step 4: Run focused tests and confirm GREEN**

Run the command from Step 2 and require zero failures.

- [ ] **Step 5: Commit**

```powershell
git add -A backend/app backend/tests frontend/src/api/handlerTransitionRules.js
git commit -m "refactor: make transition handler rules authoritative"
```

### Task 5: Update API And Frontend Status Consumers

**Files:**
- Modify: `backend/app/views/project_view.py`
- Modify: `backend/app/views/iteration_view.py`
- Modify: `backend/app/services/project_service.py`
- Modify: `backend/app/services/iteration_service.py`
- Modify: `frontend/src/views/ProjectsView.vue`
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/views/IterationDetailView.vue`
- Modify: affected frontend view-model utilities and tests

- [ ] **Step 1: Write failing contract tests**

Assert project and iteration responses include numeric definition/current-state IDs and Chinese `status_name`. Add source-contract tests that reject `project.status`, `iteration.status`, local status-code label dictionaries, and status-string filter values in migrated views.

- [ ] **Step 2: Run frontend tests and confirm RED**

```powershell
npm test
```

- [ ] **Step 3: Implement ID filters and Chinese display**

Replace status-code filter options with state options returned for the effective definition. Render `status_name` directly. History rows use `from_state_name/to_state_name` for project and iteration. Preserve Program status-label behavior unchanged.

- [ ] **Step 4: Run frontend tests and build**

```powershell
npm test
npm run build
```

Require zero test failures and a successful Vite build.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/views/project_view.py backend/app/views/iteration_view.py backend/app/services/project_service.py backend/app/services/iteration_service.py frontend
git commit -m "feat: display project and iteration states by id"
```

### Task 6: Drop Legacy Columns And Add Repository Guards

**Files:**
- Create: `backend/alembic/versions/20260717_002_remove_workflow_state_strings.py`
- Modify: `backend/app/models/workflow_definition.py`
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/models/iteration.py`
- Modify: `backend/app/db/schema.py`
- Modify: `backend/scripts/audit_workflow_state_migration.py`
- Modify: `backend/scripts/seed_demo_work_items.py`
- Modify: `backend/tests/test_model_metadata.py`
- Modify: `backend/tests/test_workflow_state_repository_guard.py`
- Modify: `backend/tests/test_project_iteration_state_migration.py`

- [ ] **Step 1: Extend failing guards and migration tests**

The guard must reject production dependencies on:

```text
Project.status
Iteration.status
WorkflowState.status_key
WorkflowTransition.from_status
WorkflowTransition.to_status
handler_transition_rules
```

Allow `Program.status`, historical snapshot field names, migration backfill code, and test fixtures explicitly.

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
python -m pytest tests/test_model_metadata.py tests/test_workflow_state_repository_guard.py tests/test_project_iteration_state_migration.py -q
```

- [ ] **Step 3: Implement destructive migration**

Before dropping anything, audit null, dangling, cross-definition, disabled-initial, invalid-transition, and enabled-orphan-rule references. Then:

```python
op.alter_column("projects", "workflow_definition_id", nullable=False)
op.alter_column("projects", "current_state_id", nullable=False)
op.alter_column("iterations", "workflow_definition_id", nullable=False)
op.alter_column("iterations", "current_state_id", nullable=False)
op.alter_column("workflow_transitions", "from_state_id", nullable=False)
op.alter_column("workflow_transitions", "to_state_id", nullable=False)
op.drop_column("projects", "status")
op.drop_column("iterations", "status")
op.drop_column("workflow_states", "status_key")
op.drop_column("workflow_transitions", "from_status")
op.drop_column("workflow_transitions", "to_status")
op.drop_table("handler_transition_rules")
```

Downgrade recreates compatibility columns from state-name snapshots or deterministic legacy aliases only for rollback mechanics; application code remains ID-only.

- [ ] **Step 4: Update models, schema bootstrap, seed and audit script**

Remove ORM columns and schema-bootstrap DDL for deleted fields/table. Make the audit script report invalid project/iteration references and confirm all deleted columns/table are absent.

- [ ] **Step 5: Run focused tests and migration round trip**

```powershell
python -m pytest tests/test_model_metadata.py tests/test_workflow_state_repository_guard.py tests/test_project_iteration_state_migration.py -q
alembic upgrade head
python scripts/audit_workflow_state_migration.py
alembic downgrade 20260717_001
alembic upgrade head
python scripts/audit_workflow_state_migration.py
```

Expected final revision: `20260717_002 (head)` and audit `ok: true` with no issues.

- [ ] **Step 6: Commit**

```powershell
git add backend
git commit -m "refactor: remove workflow state string identity"
```

### Task 7: Full Verification And Delivery Report

**Files:**
- Modify: `docs/prd/2026-07-16-workflow-end-to-end-functional-prd.md`
- Modify: `docs/reports/2026-07-16-workflow-prd-completion-report.md`
- Create: `docs/reports/2026-07-17-workflow-id-finalization-report.md`

- [ ] **Step 1: Update traceability documents**

Record the final project/iteration model, deleted columns/table, retained `Program.status`, retained `action_key`, migration evidence, and any genuinely incomplete behavior. Do not stage unrelated main-checkout edits; reconcile only the versions present in the isolated worktree.

- [ ] **Step 2: Run fresh full verification**

```powershell
cd backend
$env:DATABASE_URL='mysql+pymysql://root:root123@localhost:3306/intellective_bio_sdlc_workflow_state_model_test?charset=utf8mb4'
python -m pytest -q
python scripts/audit_workflow_state_migration.py
alembic current
cd ..\frontend
npm test
npm run build
cd ..
git diff --check
git status --short
```

Read every exit code and report warnings separately from failures.

- [ ] **Step 3: Commit documentation**

```powershell
git add docs/prd/2026-07-16-workflow-end-to-end-functional-prd.md docs/reports/2026-07-16-workflow-prd-completion-report.md docs/reports/2026-07-17-workflow-id-finalization-report.md
git commit -m "docs: report workflow id finalization"
```

- [ ] **Step 4: Review final branch**

```powershell
git log --oneline main..HEAD
git diff --check main...HEAD
git status --short --branch
```

Require a clean feature worktree and a reviewable task-by-task commit chain before integration.
