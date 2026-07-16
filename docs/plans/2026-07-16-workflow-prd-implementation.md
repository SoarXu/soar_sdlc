# Workflow PRD Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement every confirmed requirement in `docs/prd/2026-07-16-workflow-end-to-end-functional-prd.md`, covering workflow scheme creation/lifecycle, independent template copying, immutable state IDs, ID-based transitions, incremental graph persistence, and a single configured initial state.

**Architecture:** Replace status-string identity with immutable `workflow_states.id` references. A workflow definition owns its `initial_state_id`; work items own `workflow_definition_id` and `current_state_id`; transitions own `from_state_id` and `to_state_id`. Scheme creation becomes a transactional aggregate operation that creates all three object definitions either blank or as independent copies, while lifecycle transitions enforce validation and project-binding guards.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, MySQL 8, Pydantic 2, Vue 3, Element Plus, Node test scripts, pytest.

---

## Delivery Rules

- Follow TDD for every behavior change: add a focused failing test, run it and confirm the expected failure, implement the smallest change, rerun the focused test, then run the affected suite.
- Keep the legacy status-string columns only while a migration step needs them for backfill. Application code must stop reading them before the final migration removes them.
- Do not implement items listed under PRD section 9 “待后续确认”. Existing `category` behavior remains supported only to preserve current terminal gates.
- Commit after each green task so each migration stage is reviewable and reversible.

## Execution Order

The task numbers below remain aligned with the original requirement grouping, but implementation follows dependency order:

1. Task 3: establish stable state IDs and migration/backfill support.
2. Task 4: make graph persistence incremental and ID-based.
3. Task 1: add lifecycle validation on top of valid definitions and initial states.
4. Task 2: clone complete graphs using the stable ID model.
5. Tasks 5-10: migrate runtime consumers, frontend behavior, legacy cleanup, and traceability in order.

### Task 1: Workflow Scheme Lifecycle Contract

**Files:**
- Modify: `backend/app/models/assignee_rule_config.py`
- Modify: `backend/app/views/assignee_rule_config_view.py`
- Modify: `backend/app/services/assignee_rule_config_service.py`
- Modify: `backend/app/controllers/assignee_rule_config_controller.py`
- Modify: `backend/tests/test_assignee_rule_config_api.py`
- Modify: `backend/tests/test_program_project_api.py`

**Step 1: Write failing lifecycle tests**

Add tests proving:

- New blank and copied schemes start as `draft`.
- Only `enabled` schemes may be assigned to projects.
- Enabling rejects a scheme without three valid definitions and valid initial states.
- Disabling rejects a scheme while projects reference it and reports the project count.
- Disabling succeeds after all projects move away.
- `disabled` schemes are not returned as project binding options.

**Step 2: Run focused tests and confirm RED**

Run:

```powershell
python -m pytest tests/test_assignee_rule_config_api.py tests/test_program_project_api.py -q
```

Expected: failures for missing `lifecycle_status`, create mode, enable validation, and disable guard.

**Step 3: Implement lifecycle model and API**

- Add `lifecycle_status` with values `draft`, `enabled`, `disabled`.
- Replace public `enabled` mutation with explicit lifecycle actions.
- Add endpoints:
  - `POST /assignee-rule-configs/{id}/enable`
  - `POST /assignee-rule-configs/{id}/disable`
- Validate project updates so only enabled schemes can be bound.
- Keep legacy role fields unchanged for compatibility; they are not part of the new scheme creation UI.

**Step 4: Run focused tests and confirm GREEN**

Run the focused command from Step 2 and require zero failures.

**Step 5: Commit**

```powershell
git add backend/app/models/assignee_rule_config.py backend/app/views/assignee_rule_config_view.py backend/app/services/assignee_rule_config_service.py backend/app/controllers/assignee_rule_config_controller.py backend/tests/test_assignee_rule_config_api.py backend/tests/test_program_project_api.py
git commit -m "feat: add workflow scheme lifecycle"
```

### Task 2: Aggregate Scheme Creation and Independent Template Copy

**Files:**
- Modify: `backend/app/views/assignee_rule_config_view.py`
- Modify: `backend/app/services/assignee_rule_config_service.py`
- Modify: `backend/app/services/workflow_definition_service.py`
- Modify: `backend/app/services/default_workflow_template_service.py`
- Modify: `backend/app/controllers/assignee_rule_config_controller.py`
- Modify: `backend/tests/test_assignee_rule_config_api.py`
- Modify: `backend/tests/test_workflow_definition_api.py`

**Step 1: Write failing creation/copy tests**

Test these API behaviors:

- `creation_mode=blank` creates draft requirement/task/bug definitions with no states or transitions.
- `creation_mode=template` accepts one source descriptor and copies all three definitions.
- A system source and an existing scheme source use the same endpoint contract.
- Copied states, transitions, handler rules, conditions, forms, validators, UI config, and notifications match the source.
- Copied database IDs differ from source IDs.
- No source ID, project binding, runtime record, or audit history is copied or retained as lineage.
- Duplicate scheme names return 409.

**Step 2: Verify RED**

```powershell
python -m pytest tests/test_assignee_rule_config_api.py tests/test_workflow_definition_api.py -q
```

Expected: failures because aggregate creation and source listing do not exist.

**Step 3: Implement transactional aggregate creation**

- Add a unified template-source read endpoint returning system templates and existing schemes with a `source_type` display discriminator.
- Add create payload fields `creation_mode` and `template_source`.
- Create all three definitions in one transaction.
- For template mode, clone graphs with a source-state-ID to target-state-ID map.
- Generate new IDs and do not persist lineage metadata.

**Step 4: Verify GREEN and commit**

Run the focused tests, then commit:

```powershell
git add backend/app backend/tests/test_assignee_rule_config_api.py backend/tests/test_workflow_definition_api.py
git commit -m "feat: create workflow schemes from selectable templates"
```

### Task 3: ID-Based Workflow Schema and Data Migration

**Files:**
- Create: `backend/alembic/versions/20260716_001_workflow_state_identity.py`
- Modify: `backend/app/db/schema.py`
- Modify: `backend/app/models/workflow_definition.py`
- Modify: `backend/app/models/requirement.py`
- Modify: `backend/app/models/task.py`
- Modify: `backend/app/models/bug.py`
- Modify: `backend/app/models/status_operation.py`
- Modify: `backend/tests/test_model_metadata.py`
- Create: `backend/tests/test_workflow_state_migration.py`

**Step 1: Write failing metadata and migration tests**

Assert the target schema exposes:

- `workflow_definitions.initial_state_id`.
- `workflow_transitions.from_state_id` and `to_state_id`.
- `requirements/tasks/bugs.workflow_definition_id` and `current_state_id`.
- Status-operation state IDs plus immutable name snapshots for audit display.
- Foreign keys and indexes required by these references.

Add migration-fixture coverage for canonical and legacy status values, including project-specific definitions whose old state names differ from current business status strings.

**Step 2: Verify RED**

```powershell
python -m pytest tests/test_model_metadata.py tests/test_workflow_state_migration.py -q
```

**Step 3: Implement additive migration and backfill**

- Add nullable ID columns first.
- Backfill transition IDs from the owning definition and legacy status key.
- Backfill each definition’s initial state from the current `start` category.
- Resolve each work item’s effective workflow definition from its project binding, then map the legacy status to a state in that definition; support known legacy/canonical aliases.
- Backfill audit state IDs when resolvable and always preserve state-name snapshots.
- Fail migration with actionable object IDs if a work item cannot be mapped without changing business meaning.
- Add foreign keys after successful backfill.
- Add `lifecycle_status` migration and map legacy enabled values.

**Step 4: Verify migration GREEN**

Run the focused tests and execute:

```powershell
alembic upgrade head
alembic current
```

Expected revision: `20260716_001`.

**Step 5: Commit**

```powershell
git add backend/alembic backend/app/db/schema.py backend/app/models backend/tests/test_model_metadata.py backend/tests/test_workflow_state_migration.py
git commit -m "feat: migrate workflows to state identity references"
```

### Task 4: Incremental Graph API and Stable State IDs

**Files:**
- Modify: `backend/app/views/workflow_definition_view.py`
- Modify: `backend/app/services/workflow_definition_service.py`
- Modify: `backend/app/services/default_workflow_template_service.py`
- Modify: `backend/tests/test_workflow_definition_api.py`
- Modify: `backend/tests/test_default_workflow_templates_api.py`

**Step 1: Write failing graph persistence tests**

Prove that:

- Graph reads expose state IDs, state names, transition state IDs, and `initial_state_id` without status keys.
- New unsaved states may use temporary negative IDs in a save request.
- Saving updates existing nodes in place and preserves positive IDs.
- New nodes receive new positive IDs and all transition/initial references are remapped.
- Omitted unreferenced states are deleted.
- Omitted referenced states are disabled rather than deleted.
- Initial state must be enabled and belong to the definition.
- Duplicate or cross-definition references are rejected.

**Step 2: Verify RED**

```powershell
python -m pytest tests/test_workflow_definition_api.py tests/test_default_workflow_templates_api.py -q
```

**Step 3: Implement the ID graph contract**

- Replace `status_key`, `from_status`, and `to_status` in public graph schemas with IDs.
- Accept negative temporary state IDs and resolve them transactionally.
- Incrementally update states and transitions.
- Make default-template reconciliation compare and update nodes without replacing IDs.
- Store initial state on the definition.

**Step 4: Verify GREEN and commit**

```powershell
git add backend/app/views/workflow_definition_view.py backend/app/services/workflow_definition_service.py backend/app/services/default_workflow_template_service.py backend/tests/test_workflow_definition_api.py backend/tests/test_default_workflow_templates_api.py
git commit -m "feat: persist workflow graphs by immutable state id"
```

### Task 5: ID-Based Workflow Runtime and Work Item Creation

**Files:**
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/services/status_operation_service.py`
- Modify: `backend/app/services/requirement_service.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/services/bug_service.py`
- Modify: `backend/app/views/requirement_view.py`
- Modify: `backend/app/views/task_view.py`
- Modify: `backend/app/views/bug_view.py`
- Modify: `backend/app/views/workflow_runtime_view.py`
- Modify: `backend/tests/test_workflow_runtime_api.py`
- Modify: `backend/tests/test_requirement_task_api.py`
- Modify: `backend/tests/test_bug_workflow_api.py`

**Step 1: Write failing runtime tests**

Cover:

- New work items resolve the effective definition and always enter `initial_state_id` regardless of selected owner.
- Responses expose `current_state_id` and `status_name`.
- Available actions match `from_state_id`.
- Execution writes `to_state_id`, keeps workflow definition ownership consistent, and logs state IDs/name snapshots.
- Handler assignment does not implicitly choose a different initial state.
- Reactivation and conditional routes select state IDs.
- A project-bound invalid definition fails with an explicit diagnostic and never falls back silently.

**Step 2: Verify RED**

```powershell
python -m pytest tests/test_workflow_runtime_api.py tests/test_requirement_task_api.py tests/test_bug_workflow_api.py -q
```

**Step 3: Implement ID runtime**

- Resolve state objects, not status strings.
- Use transition state IDs for action discovery and execution.
- Make creation use definition `initial_state_id` in all three services.
- Preserve existing owner-routing behavior without letting owner selection alter initial state.
- Store audit state IDs and snapshots.
- Replace status-name-specific bug routing with transition-local state-ID routing.

**Step 4: Verify GREEN and commit**

```powershell
git add backend/app/services backend/app/views backend/tests/test_workflow_runtime_api.py backend/tests/test_requirement_task_api.py backend/tests/test_bug_workflow_api.py
git commit -m "feat: execute workflows by state identity"
```

### Task 6: Remove Runtime Status-String Dependencies

**Files:**
- Modify: `backend/app/services/dashboard_service.py`
- Modify: `backend/app/services/work_item_service.py`
- Modify: `backend/app/services/exception_center_service.py`
- Modify: `backend/app/services/iteration_service.py`
- Modify: `backend/app/services/project_service.py`
- Modify: `backend/app/services/validation_case_service.py`
- Modify: `backend/app/services/handler_transition_rule_service.py`
- Modify: affected backend view models and tests

**Step 1: Write failing behavior tests**

Add/adjust tests proving:

- Workbench grouping and unassigned lists use state properties and current-state relationships, not hard-coded status strings.
- Requirement/Bug/iteration/project gates inspect current state category through relationships.
- Exception evaluation receives state ID/name context.
- State-name changes do not change queue membership, gate outcomes, or action availability.

**Step 2: Verify RED with affected suites**

```powershell
python -m pytest tests/test_dashboard_workbench_api.py tests/test_unassigned_work_items_api.py tests/test_exception_center_api.py tests/test_iteration_detail_api.py tests/test_program_project_api.py -q
```

**Step 3: Refactor runtime consumers**

- Introduce shared state lookup helpers.
- Replace entity `.status` comparisons with current-state records or category checks.
- Keep exact business action semantics in transition/action configuration rather than status names.

**Step 4: Verify GREEN and commit**

```powershell
git add backend/app backend/tests
git commit -m "refactor: remove status string runtime dependencies"
```

### Task 7: Frontend Scheme Creation and Lifecycle UI

**Files:**
- Modify: `frontend/src/api/assigneeRuleConfigs.js`
- Modify: `frontend/src/views/WorkflowView.vue`
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Create: `frontend/src/utils/workflowSchemeCreation.js`
- Create: `frontend/src/utils/workflowSchemeCreation.test.mjs`
- Modify: `frontend/scripts/run-tests.mjs`
- Modify: `frontend/src/styles.css`

**Step 1: Write failing frontend tests**

Test source-level/view-model behavior for:

- Blank versus template creation modes.
- One template selector containing system templates and existing schemes with type labels.
- New scheme name/description independent from source.
- Draft status after creation.
- Only enabled schemes in project selectors.
- Enable validation feedback and disable project-count feedback.
- No source-lineage display.

**Step 2: Verify RED**

```powershell
npm test
```

Expected: new test fails because creation helpers and lifecycle UI are absent.

**Step 3: Implement UI**

- Replace the current single form with a creation mode selector and conditional template source selector.
- Show lifecycle status badges and context-appropriate actions.
- Remove the old boolean switch.
- Filter project binding selectors to enabled schemes.
- Keep project-transfer workflow explicit before disable.

**Step 4: Verify GREEN and commit**

```powershell
npm test
npm run build
git add frontend
git commit -m "feat: add workflow scheme creation and lifecycle ui"
```

### Task 8: Frontend ID-Based Designer and Business Status Display

**Files:**
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Modify: `frontend/src/components/WorkflowAdvancedConfigDrawer.vue`
- Modify: `frontend/src/utils/workflowTransitionConfig.js`
- Modify: `frontend/src/utils/workflowAdvancedConfig.js`
- Modify: relevant utility tests
- Modify: requirement/task/bug list and detail views
- Modify: `frontend/src/utils/workbenchViewModel.js`

**Step 1: Write failing frontend tests**

Prove:

- Designer uses immutable numeric state IDs and negative temporary IDs.
- Initial state selection saves `initial_state_id`.
- Renaming `status_name` preserves transitions.
- Removing a referenced state results in a disabled state response.
- Lists/details/workbench display backend `status_name` and do not translate status codes locally.

**Step 2: Verify RED**

```powershell
npm test
```

**Step 3: Implement designer and display migration**

- Key state selection and edge construction by numeric ID.
- Add initial-state selector at definition level.
- Remove editable status-code controls.
- Submit ID-based condition routes.
- Replace frontend status label dictionaries with returned state names.

**Step 4: Verify GREEN and commit**

```powershell
npm test
npm run build
git add frontend
git commit -m "feat: use workflow state ids in frontend"
```

### Task 9: Destructive Legacy Cleanup and Full Migration Audit

**Files:**
- Modify: `backend/alembic/versions/20260716_001_workflow_state_identity.py`
- Modify: backend models/views/services still referencing legacy columns
- Modify: remaining backend/frontend tests
- Create: `backend/scripts/audit_workflow_state_migration.py`

**Step 1: Add failing repository guard tests**

Add tests or source scans that fail while production code still depends on:

- `requirements/tasks/bugs.status`.
- `workflow_states.status_key`.
- `workflow_transitions.from_status/to_status`.
- Local frontend status-code label maps for migrated objects.

**Step 2: Verify RED**

Run repository tests and confirm guard failures list remaining references.

**Step 3: Remove legacy columns and references**

- Drop migrated string identity columns after all runtime reads are gone.
- Keep explicit name snapshots only in audit history.
- Update seed/demo scripts and docs.
- Add a read-only audit script that reports null/invalid definition, state, transition, and initial-state references.

**Step 4: Run migration audit and full verification**

```powershell
python scripts/audit_workflow_state_migration.py
python -m pytest -q
cd ..\frontend
npm test
npm run build
```

Expected:

- Audit reports zero invalid references.
- Backend has zero failures.
- Frontend has zero test failures.
- Production build succeeds.

**Step 5: Commit**

```powershell
git add backend frontend docs
git commit -m "refactor: remove legacy workflow status identity"
```

### Task 10: PRD Traceability and Completion Report

**Files:**
- Modify: `docs/prd/2026-07-16-workflow-end-to-end-functional-prd.md`
- Create: `docs/reports/2026-07-16-workflow-prd-completion-report.md`

**Step 1: Audit every confirmed PRD requirement**

Create a matrix for FR-1 through FR-13 with implementation files, test evidence, status, and residual risk.

**Step 2: Record incomplete items truthfully**

Any unmet acceptance criterion must be marked `未完成` or `部分完成` with the concrete reason. Do not classify PRD section 9 open decisions as incomplete implementation.

**Step 3: Run final fresh verification**

```powershell
cd backend
python -m pytest -q
python scripts/audit_workflow_state_migration.py
cd ..\frontend
npm test
npm run build
git diff --check
git status --short
```

**Step 4: Commit documentation**

```powershell
git add docs
git commit -m "docs: report workflow prd implementation status"
```
