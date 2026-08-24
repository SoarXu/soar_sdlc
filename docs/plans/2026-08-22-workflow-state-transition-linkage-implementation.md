# Workflow State Transition Linkage Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the visible state deletion entry and keep transition availability consistent with the enabled state of both endpoint states without restoring manually disabled transitions.

**Architecture:** Persist an `auto_disabled_by_state` reason flag on each workflow transition. Apply the same deterministic synchronization rule in a pure frontend helper for immediate canvas feedback and in the backend graph-save boundary for authoritative consistency; existing disabled-edge rendering remains unchanged.

**Tech Stack:** Vue 3, Element Plus, JavaScript/Node tests, FastAPI, Pydantic, SQLAlchemy, Alembic, MySQL, pytest.

---

## Execution Rules

- Use @test-driven-development for every behavior change: add one focused failing test, run it and confirm the expected failure, then implement the minimum production change.
- Use @systematic-debugging if a test fails for a reason other than the intended missing behavior.
- Use @verification-before-completion before changing the issue status or claiming completion.
- Work in the current workspace because the approved design and issue record already exist here.
- Do not commit, push, merge, or create a PR during these tasks. The repository instructions require explicit delivery confirmation after implementation and verification.
- Preserve unrelated existing changes in `issue.md`, `deploy/`, and `deploy.tar.gz`.

### Task 1: Add the transition disable-reason field

**Files:**
- Create: `backend/alembic/versions/20260822_001_workflow_transition_state_disable_reason.py`
- Create: `backend/tests/test_workflow_transition_state_disable_reason_migration.py`
- Modify: `backend/app/models/workflow_definition.py:62-98`
- Modify: `backend/app/views/workflow_definition_view.py:61-98`
- Modify: `backend/app/db/schema.py:506-540`

**Step 1: Write the failing migration and contract tests**

Add tests that require:

```python
assert migration.revision == "20260822_001"
assert migration.down_revision == "20260819_008"
assert "auto_disabled_by_state" in migration source/upgrade operations
assert WorkflowTransition.__table__.c.auto_disabled_by_state.default.arg is False
assert WorkflowTransitionRead.model_validate(transition).auto_disabled_by_state is False
```

Also assert that `WorkflowTransitionSave` accepts an explicit `auto_disabled_by_state=True` value and that the fallback schema creates or ensures the same non-null boolean column.

**Step 2: Run the tests to verify RED**

Run:

```bash
cd backend
pytest tests/test_workflow_transition_state_disable_reason_migration.py -q
```

Expected: FAIL because the migration, model field, API field, and fallback schema support do not exist.

**Step 3: Implement the migration and contracts**

Create an Alembic migration with:

```python
revision = "20260822_001"
down_revision = "20260819_008"

def upgrade() -> None:
    op.add_column(
        "workflow_transitions",
        sa.Column(
            "auto_disabled_by_state",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )

def downgrade() -> None:
    op.drop_column("workflow_transitions", "auto_disabled_by_state")
```

Add the SQLAlchemy field with Python and server defaults:

```python
auto_disabled_by_state: Mapped[bool] = mapped_column(
    Boolean,
    default=False,
    server_default=text("0"),
)
```

Expose the field through the transition read/save contract with a default of `False`. Add the column to the initial `CREATE TABLE workflow_transitions` SQL and add an `_ensure_column` call for databases initialized through `schema.py`.

**Step 4: Run the tests to verify GREEN**

Run:

```bash
cd backend
pytest tests/test_workflow_transition_state_disable_reason_migration.py -q
python -m compileall -q app alembic/versions/20260822_001_workflow_transition_state_disable_reason.py
```

Expected: all focused tests pass and compilation exits with code 0.

**Step 5: Git checkpoint**

Do not commit. Record the changed paths for the final delivery prompt.

### Task 2: Enforce state-transition consistency in graph saves

**Files:**
- Modify: `backend/app/services/workflow_definition_service.py:139-148`
- Modify: `backend/app/services/workflow_definition_service.py:404-470`
- Modify: `backend/app/services/workflow_definition_service.py:682-758`
- Modify: `backend/tests/test_workflow_definition_api.py`

**Step 1: Write failing API tests**

Add focused tests that create two or three states and transitions, save once to obtain positive IDs, and then verify:

1. Disabling either endpoint automatically sets an enabled transition to `enabled=false` and `auto_disabled_by_state=true`.
2. A transition already saved as manually disabled with `auto_disabled_by_state=false` remains unmarked when an endpoint is disabled.
3. Restoring only one of two disabled endpoints keeps an automatically disabled transition disabled and marked.
4. Restoring both endpoints re-enables only the marked transition and clears its marker.
5. An old-style update payload that omits `auto_disabled_by_state` preserves the persisted marker before applying the endpoint rule.
6. A new transition submitted as enabled between disabled endpoints is normalized to disabled and marked.

Do not assert only response values; reopen a `SessionLocal` session and assert persisted column values.

**Step 2: Run the tests to verify RED**

Run:

```bash
cd backend
pytest tests/test_workflow_definition_api.py -q -k "state_disable or auto_disabled"
```

Expected: FAIL because graph saves currently persist transition `enabled` independently from endpoint states.

**Step 3: Implement authoritative normalization**

Before `_validate_graph`, load existing transitions and resolve the marker for every submitted transition:

```python
def _synchronize_transition_state_availability(db, definition, payload):
    state_enabled = {item.id: item.enabled for item in payload.states}
    existing = {
        item.id: item
        for item in db.query(WorkflowTransition)
        .filter(WorkflowTransition.definition_id == definition.id)
        .all()
    }
    for transition in payload.transitions:
        if "auto_disabled_by_state" in transition.model_fields_set:
            marker = transition.auto_disabled_by_state
        else:
            marker = bool(getattr(existing.get(transition.id), "auto_disabled_by_state", False))
        endpoints_enabled = (
            state_enabled[transition.from_state_id]
            and state_enabled[transition.to_state_id]
        )
        if not endpoints_enabled:
            if transition.enabled:
                marker = True
            transition.enabled = False
        elif marker:
            transition.enabled = True
            marker = False
        transition.auto_disabled_by_state = marker
```

Call the helper from `save_graph` after legacy reference normalization and before `_save_graph` validation. Ensure `_persist_graph` writes the resolved boolean for new and existing transitions.

The helper must not infer that every disabled transition is automatic. Only an enabled transition forced off by an inactive endpoint receives the marker.

**Step 4: Run the tests to verify GREEN**

Run:

```bash
cd backend
pytest tests/test_workflow_definition_api.py -q -k "state_disable or auto_disabled"
```

Expected: all new state-transition consistency tests pass.

**Step 5: Run adjacent backend regression tests**

Run:

```bash
cd backend
pytest tests/test_workflow_definition_api.py tests/test_workflow_runtime_api.py tests/test_default_workflow_templates_api.py -q
```

Expected: all selected workflow tests pass.

**Step 6: Git checkpoint**

Do not commit. Record the changed paths for the final delivery prompt.

### Task 3: Add the pure frontend linkage model

**Files:**
- Create: `frontend/src/utils/workflowStateAvailability.js`
- Create: `frontend/src/utils/workflowStateAvailability.test.mjs`

**Step 1: Write the failing pure-function tests**

Define the wished-for API:

```javascript
const result = setWorkflowStateEnabled(states, transitions, stateId, false)
```

Assert that the function:

- returns updated state and transition arrays without mutating inputs;
- disables every incoming, outgoing, and self-transition that was enabled and sets `auto_disabled_by_state: true`;
- leaves unrelated transitions unchanged;
- keeps manually disabled transitions disabled and unmarked;
- waits for both endpoint states to be enabled before restoring a marked transition;
- restores and clears only marked transitions after both endpoints recover;
- preserves all transitions in the returned collection so disabled edges remain renderable.

**Step 2: Run the test to verify RED**

Run:

```bash
cd frontend
node src/utils/workflowStateAvailability.test.mjs
```

Expected: FAIL with module-not-found or missing export for `setWorkflowStateEnabled`.

**Step 3: Implement the minimal pure function**

Implement immutable synchronization using an endpoint-enabled map. The central transition rule should be equivalent to:

```javascript
if (!endpointsEnabled) {
  return {
    ...transition,
    enabled: false,
    auto_disabled_by_state: transition.auto_disabled_by_state || transition.enabled
  }
}
if (transition.auto_disabled_by_state) {
  return { ...transition, enabled: true, auto_disabled_by_state: false }
}
return { ...transition }
```

Keep the helper independent from Vue and DOM APIs.

**Step 4: Run the test to verify GREEN**

Run:

```bash
cd frontend
node src/utils/workflowStateAvailability.test.mjs
```

Expected: `workflow state availability tests passed`.

**Step 5: Git checkpoint**

Do not commit. Record the changed paths for the final delivery prompt.

### Task 4: Remove the button and connect state toggles

**Files:**
- Modify: `frontend/src/components/WorkflowAdvancedConfigDrawer.vue:28-51`
- Modify: `frontend/src/components/WorkflowAdvancedConfigDrawer.vue:104-130`
- Modify: `frontend/src/components/WorkflowAdvancedConfigDrawer.vue:403-417`
- Modify: `frontend/src/components/WorkflowDesigner.vue:178-197`
- Modify: `frontend/src/components/WorkflowDesigner.vue:727-751`
- Modify: `frontend/src/components/workflowDesignerDrawerIntegration.test.mjs`
- Verify: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`

**Step 1: Change the component contract test first**

Replace the old assertions requiring the delete-state button/event with assertions that:

```javascript
assert.doesNotMatch(drawer, />\s*删除状态\s*</)
assert.match(drawer, /@update:model-value="requestStateEnabledChange"/)
assert.match(drawer, /emit\('state-enabled-change'/)
assert.match(designer, /@state-enabled-change="setSelectedStateEnabled"/)
assert.match(designer, /setWorkflowStateEnabled/)
assert.match(designer, /disabled: !edge\.transition\.enabled/)
```

Also require the transition enable switch to be disabled when either endpoint is inactive. Per the approved scope, remove only the visible delete-state button; do not add a replacement delete command or backend deletion path.

**Step 2: Run the component test to verify RED**

Run:

```bash
cd frontend
node src/components/workflowDesignerDrawerIntegration.test.mjs
```

Expected: FAIL because the delete-state button still exists and state toggles do not invoke linkage logic.

**Step 3: Implement the component wiring**

In the state form:

```vue
<el-switch
  :model-value="state.enabled"
  @update:model-value="requestStateEnabledChange"
/>
```

Remove the visible `删除状态` button. Emit `state-enabled-change` from a small drawer handler. In `WorkflowDesigner.vue`, call the pure helper and replace `states.value` and `transitions.value` with its result.

For transition editing, compute whether both endpoint states are enabled and bind that result to the transition enable switch's `disabled` property. Do not filter disabled transitions from `canvasProjection` or `transitionViews`; retain the existing `.workflow-edge.disabled` dashed presentation.

**Step 4: Run focused frontend tests to verify GREEN**

Run:

```bash
cd frontend
node src/utils/workflowStateAvailability.test.mjs
node src/components/workflowDesignerDrawerIntegration.test.mjs
node src/components/workflowDesignerAutoLayout.test.mjs
node src/utils/workflowCanvasProjection.test.mjs
```

Expected: all four commands pass; the projection test confirms disabled transitions remain available to the canvas.

**Step 5: Git checkpoint**

Do not commit. Record the changed paths for the final delivery prompt.

### Task 5: Run migration and full regression verification

**Files:**
- Verify only.

**Step 1: Verify the migration chain and backend syntax**

Run:

```bash
cd backend
alembic heads
python -m compileall -q app alembic/versions/20260822_001_workflow_transition_state_disable_reason.py
```

Expected: exactly one Alembic head, `20260822_001`, and compilation exits with code 0.

**Step 2: Run the backend workflow regression**

Run:

```bash
cd backend
pytest tests/test_workflow_transition_state_disable_reason_migration.py tests/test_workflow_definition_api.py tests/test_workflow_runtime_api.py tests/test_default_workflow_templates_api.py -q
```

Expected: all selected tests pass with zero failures.

**Step 3: Run all frontend tests**

Run:

```bash
cd frontend
npm test
```

Expected: the test runner exits with code 0 and includes the new state-availability test.

**Step 4: Build the production frontend**

Run:

```bash
cd frontend
npm run build
```

Expected: Vite production build exits with code 0.

**Step 5: Check the complete diff**

Run from repository root:

```bash
git diff --check
git status --short
```

Expected: `git diff --check` exits with code 0. Status contains only the known pre-existing changes and files created or modified by this issue.

### Task 6: Update the issue record after implementation

**Files:**
- Modify: `docs/issues/2026-08-22-后续问题清单.md`

**Step 1: Record fresh verification evidence**

After all required commands pass, change N-001 from `待实施` to `待验证` and replace `尚未实施` with exact test counts, migration head output, build result, and any environment limitations. Do not mark the issue `已解决` until product acceptance is complete.

**Step 2: Verify documentation integrity**

Run:

```bash
git diff --check -- docs/issues/2026-08-22-后续问题清单.md docs/plans/2026-08-22-workflow-state-transition-linkage-design.md docs/plans/2026-08-22-workflow-state-transition-linkage-implementation.md
```

Expected: exit code 0.

**Step 3: Request delivery confirmation**

Report all modified files and verification evidence, then ask the repository-mandated five-option Git delivery question. Perform no Git commit, push, PR, or merge until the user explicitly chooses an option.
