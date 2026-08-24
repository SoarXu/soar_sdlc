# Work Item State Matrix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make requirement, task, and Bug creation plus assignment follow the owner/iteration state matrix, with auditable automatic activation when an iteration starts.

**Architecture:** Persist a stable `state_role` on workflow states and resolve it in backend services instead of inspecting display names. Default templates and recognized existing definitions receive `unassigned`, `waiting_iteration`, and `active_work`; runtime routing invokes existing transition execution for visible ownership actions and hidden system activation actions.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, Vue 3, Element Plus, pytest, Node source-contract tests.

---

## Task 1: Persist and validate workflow state roles

**Files:**

- Create: `backend/alembic/versions/20260822_002_work_item_state_roles.py`
- Modify: `backend/app/models/workflow_definition.py`
- Modify: `backend/app/views/workflow_definition_view.py`
- Modify: `backend/app/db/schema.py`
- Modify: `backend/app/services/workflow_definition_service.py`
- Create: `backend/tests/test_workflow_state_role_migration.py`
- Modify: `backend/tests/test_workflow_definition_api.py`

1. Write failing tests for migration revision, non-null role values when supplied, graph API read/save round-trip, duplicate role rejection, and role validity by object type.
2. Run the focused tests and confirm they fail because the column and contracts do not exist.
3. Add nullable `state_role VARCHAR(32)`, indexed by `(definition_id, state_role)`; add a database/model/API contract; permit only `unassigned`, `waiting_iteration`, and `active_work` for requirement/task/Bug states and reject duplicate non-null roles.
4. Add role-preservation rules to graph persistence so old payloads do not erase an existing role unless the field is explicitly supplied.
5. Rerun focused tests and compile the changed backend modules.

## Task 2: Upgrade default and recognized existing workflows

**Files:**

- Modify: `backend/app/services/default_workflow_template_service.py`
- Modify: `backend/app/services/workflow_definition_service.py`
- Modify: `backend/alembic/versions/20260822_002_work_item_state_roles.py`
- Create: `backend/tests/test_work_item_state_matrix_migration.py`

1. Write failing tests that build legacy requirement/task/Bug graphs and verify exactly one waiting state, role assignments, assignment routing, cancel-assignment transitions, and a hidden iteration-start transition after upgrade.
2. Run them to establish the legacy graph lacks the new semantic roles and paths.
3. Extend template state metadata with `state_role`; add waiting states and route assignment/claim by iteration phase. Add a hidden `start_iteration` system action from waiting to active and a visible cancel-assignment action from waiting/active to unassigned.
4. Add an idempotent reconciliation routine for recognized existing definitions. It must use action keys and structural evidence, never runtime display-name matching, and leave ambiguous custom graphs unchanged with a configuration error path.
5. Run migration/reconciliation tests plus default-template regression tests.

## Task 3: Resolve state roles for creation and ownership transitions

**Files:**

- Modify: `backend/app/services/workflow_state_service.py`
- Modify: `backend/app/services/requirement_service.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/services/bug_service.py`
- Modify: `backend/app/services/workflow_runtime_service.py`
- Create: `backend/tests/test_work_item_state_matrix_api.py`

1. Write API tests covering all six creation cells for requirement, task and Bug, plus assignment in planned/active iterations and cancellation of an assignment.
2. Confirm RED: current services always choose `definition.initial_state_id` and runtime cannot resolve the phase-dependent target.
3. Add a single role resolver that takes object type, project/component context, owner and iteration. It must return `unassigned`, `waiting_iteration`, or `active_work` from the effective definition, with structured errors for missing/ambiguous required roles.
4. Use this resolver in every creation path, including linked tasks and Bugs created from failed test run cases. Extend runtime target resolution with an internal iteration-phase role route; do not hard-code Chinese status names.
5. Add and configure `unassign` to clear the owner and return the state to `unassigned`; retain audit history through the existing runtime transition path.
6. Run matrix API tests and adjacent creation/runtime regressions.

## Task 4: Synchronize iteration start and iteration moves

**Files:**

- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/services/work_item_iteration_history_service.py`
- Modify: `backend/app/services/requirement_service.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/services/bug_service.py`
- Modify: `backend/app/services/iteration_service.py`
- Extend: `backend/tests/test_work_item_state_matrix_api.py`

1. Write failing tests for iteration start with unassigned and waiting items, for automatic start after a waiting item moves into an active iteration, and for rejection when active work is moved to an unstarted iteration.
2. Ensure the iteration’s current state is changed to active before system-running Bug transitions, so the existing Bug iteration guard remains valid.
3. Execute the hidden activation transition using `_execute_transition(..., allow_system_action=True, inherit_parent_permission=True, commit=False)` in the same transaction and preserve the initiating actor in status-operation history.
4. Centralize move-direction validation and post-move activation. Requirement-dependent task/Bug moves must validate as a batch before mutating any membership row, preserving all-or-nothing behavior.
5. Run focused tests plus iteration-history and workflow runtime regressions.

## Task 5: Expose roles in the workflow designer

**Files:**

- Modify: `frontend/src/components/WorkflowAdvancedConfigDrawer.vue`
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Extend: `frontend/src/components/workflowDesignerDrawerIntegration.test.mjs`
- Create: `frontend/src/utils/workflowStateRoles.js`
- Create: `frontend/src/utils/workflowStateRoles.test.mjs`

1. Add a failing helper/component contract test for object-type-specific role options and `state_role` round-trip.
2. Add the state-role selector only for requirement/task/Bug. Preserve null for non-system states and do not expose roles for project or iteration graphs.
3. Ensure graph serialization retains `state_role`, and show duplicate/invalid API messages through existing save error feedback.
4. Run focused Node tests, all frontend tests, and a production build.

## Task 6: Verification and issue record

1. Run Alembic head/upgrade checks, migration tests, state-matrix API tests, workflow-definition/runtime/default-template/iteration-history regressions, frontend tests, build, and `git diff --check`.
2. Update N-002 to `已解决` with exact counts and any unrelated baseline limitations only after the state matrix has passed all targeted evidence.
3. Do not commit, merge, push, or restart services until all N-001 through N-007 are complete and the user-authorized delivery phase is reached.
