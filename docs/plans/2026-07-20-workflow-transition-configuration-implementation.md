# Workflow Transition Configuration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace public workflow action keys with transition IDs and add state-scoped button grouping and drag sorting while preserving the existing fixed runtime behavior.

**Architecture:** Keep `action_key` as a private backend compatibility field, but make runtime discovery and execution use `transition_id`. Normalize button metadata to `list_display + sort_order`, protect persisted transitions from hard deletion, and rebuild the designer around one state/transition drawer with draft-only drag operations.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, Vue 3, Element Plus, native HTML drag events, Node test runner, Pytest.

---

### Task 1: Runtime transition identity

**Files:**
- Modify: `backend/app/views/workflow_runtime_view.py`
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/services/project_service.py`
- Test: `backend/tests/test_workflow_runtime_api.py`
- Test: `backend/tests/test_project_iteration_state_migration.py`

**Steps:**

1. Add failing API tests asserting discovery returns `transition_id` without `action_key` or `list_priority`, and execution accepts only `transition_id`.
2. Add failing tests for unknown, disabled, cross-definition and stale-source transition IDs.
3. Run `pytest backend/tests/test_workflow_runtime_api.py -q` and confirm the new assertions fail.
4. Change the Pydantic runtime views to expose `transition_id` and `sort_order`; replace the execute request `action_key` with `transition_id`.
5. Load executable transitions by ID plus the current definition and state, then run existing condition and permission validation before using the private action key.
6. Update internal project service calls to resolve a transition record and pass its ID.
7. Run the focused backend tests and confirm they pass.

### Task 2: Definition validation and persisted transition protection

**Files:**
- Modify: `backend/app/views/workflow_definition_view.py`
- Modify: `backend/app/services/workflow_definition_service.py`
- Test: `backend/tests/test_workflow_definition_api.py`

**Steps:**

1. Add failing tests proving new transitions do not require a client action key, duplicate enabled names under one source are rejected, illegal button groups are rejected, and persisted transitions cannot be omitted.
2. Run `pytest backend/tests/test_workflow_definition_api.py -q` and confirm the tests fail.
3. Split transition create/update input semantics so action keys are not accepted from the administrator payload.
4. Generate a neutral unique internal action key for new records and preserve existing keys during updates.
5. Validate `list_display` as `primary|more`, remove obsolete UI keys, and validate enabled-name uniqueness per source state.
6. Replace omitted-transition deletion with a 422 response while still allowing unsaved negative-ID transitions to be removed client-side.
7. Run the focused definition tests and confirm they pass.

### Task 3: Existing button configuration migration

**Files:**
- Create: `backend/alembic/versions/20260720_001_normalize_workflow_transition_buttons.py`
- Modify: `backend/app/services/default_workflow_template_service.py`
- Test: `backend/tests/test_model_metadata.py`
- Test: `backend/tests/test_default_workflow_templates_api.py`

**Steps:**

1. Add migration-level tests or static assertions for normalization behavior.
2. Write an Alembic data migration that converts both hidden forms to `enabled=false`, removes obsolete UI keys, assigns `more` to illegal/missing groups, and rewrites group-local `sort_order` using old priority/order/ID.
3. Update default templates to stop emitting `list_priority` and assign meaningful `sort_order` values directly.
4. Run migration and template tests.
5. Upgrade the local database to the new head and verify Alembic reports one head.

### Task 4: Frontend runtime action grouping

**Files:**
- Modify: `frontend/src/api/workflowRuntime.js`
- Modify: `frontend/src/utils/workflowRuntimeActions.js`
- Modify: `frontend/src/utils/workflowRuntimeActions.test.mjs`
- Modify: `frontend/src/components/WorkflowActionButtons.vue`
- Modify: list views containing workflow operation columns

**Steps:**

1. Rewrite frontend utility tests to use `transition_id`, `sort_order`, multiple primary actions, no hidden filtering and no automatic promotion.
2. Run `npm test -- --filter workflowRuntimeActions` from `frontend` and confirm failure.
3. Implement deterministic `primaryActions` and `moreActions` grouping using `list_display`, `sort_order` and `transition_id`.
4. Update buttons, loading state, dropdown commands and execute payloads to use transition IDs.
5. Render all primary buttons in one non-wrapping row on list and detail pages.
6. Replace fixed operation-column widths with measured/adaptive minimum widths and preserve table horizontal scrolling.
7. Run frontend tests and production build.

### Task 5: State action drawer and drag sorting

**Files:**
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Modify: `frontend/src/components/WorkflowAdvancedConfigDrawer.vue`
- Modify: `frontend/src/utils/workflowTransitionConfig.js`
- Modify: `frontend/src/utils/workflowTransitionConfig.test.mjs`
- Create: `frontend/src/utils/workflowTransitionOrdering.js`
- Create: `frontend/src/utils/workflowTransitionOrdering.test.mjs`

**Steps:**

1. Add failing pure-function tests for state-scoped grouping, group-local renumbering, group-to-group moves, new-transition placement and re-enable placement.
2. Run frontend tests and confirm the new tests fail.
3. Implement pure ordering helpers with `sort_order` increments of 10.
4. Replace the fixed right inspector and nested advanced drawer with one drawer that switches between state action groups and transition detail.
5. Add drag handles, native drag events, empty-group drop zones and per-group add buttons.
6. Hide disabled transitions from group lists; render disabled graph edges as gray dashed lines and route edge clicks to detail.
7. Remove action-key editing, global add-transition, hard deletion for persisted transitions, free-form field editing and obsolete visibility controls.
8. Preserve all edits as local graph draft until the existing save action succeeds.
9. Run component utility tests and production build.

### Task 6: End-to-end regression and visual verification

**Files:**
- Modify as required by test failures only.

**Steps:**

1. Run `pytest -q` from `backend` and fix regressions without restoring public action-key behavior.
2. Run `npm test` and `npm run build` from `frontend`.
3. Start backend and frontend development servers on free local ports.
4. Verify with the browser at desktop and narrow viewports: state drawer navigation, multiple primary actions, cross-group drag, save/reload persistence, disabled dashed edge, list/detail grouping and horizontal table scrolling.
5. Check browser console and backend logs for errors.
6. Record exact test, build, migration and visual-verification results in the final handoff.
