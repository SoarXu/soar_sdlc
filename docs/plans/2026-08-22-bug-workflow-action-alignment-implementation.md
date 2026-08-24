# Bug Workflow Action Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align Bug assignment and edit actions with the N-002 state-role matrix across new templates, deployed default workflows, and every Bug UI surface.

**Architecture:** Treat N-002 stable state roles as the only source for locating unassigned, waiting-iteration, and active-work states. Update the default Bug graph and an idempotent managed-definition migration, then route the project-detail Bug edit command to its existing editor while preserving the already-correct global list and detail handlers.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, Alembic, pytest, Vue 3, Element Plus, Node.js source-contract tests, Vite.

---

## Execution Rules

- Prerequisite: complete and verify N-002 before starting this plan. Stop if the N-002 stable state-role field/helper or migrated Bug states are absent.
- Use @test-driven-development for every behavior change: write the focused failing test, verify RED, implement the minimum change, then verify GREEN.
- Use @systematic-debugging for unrelated or ambiguous failures.
- Use @verification-before-completion before updating N-004 or claiming success.
- Work in the current workspace because the issue and plan documents already live here.
- Do not commit, push, merge, or create a PR until the repository-mandated delivery confirmation is answered. The commit steps below are proposed checkpoints to execute only after the user selects a Git delivery option.
- Preserve unrelated changes in `issue.md`, `deploy/`, `deploy.tar.gz`, and other 2026-08-22 issue documents.

### Task 1: Lock the N-002-based Bug action matrix with failing tests

**Files:**
- Modify: `backend/tests/test_default_workflow_templates_api.py:400-530`
- Read: `backend/app/services/default_workflow_template_service.py:641-860`
- Read: N-002 state-role implementation files introduced before this plan

**Step 1: Add a helper that resolves states by stable role**

In the test module, resolve the current state using the N-002 stable role field/helper rather than `status_name`. Reuse the production role constants instead of spelling editable Chinese names in selectors.

**Step 2: Add the desired matrix assertions**

For Bug records placed in each stable role, assert:

```python
assert {"claim", "assign", "edit"} <= unassigned_actions
assert {"transfer", "change_handler"}.isdisjoint(unassigned_actions)

assert {"transfer", "change_handler", "edit"} <= waiting_iteration_actions

assert {"transfer", "change_handler"} <= active_work_actions
assert "edit" not in active_work_actions
```

Also assert that edit is absent from review, verification, verified, and closed states. Use appropriate authenticated identities for each action because runtime role and owner filters intentionally produce different action sets.

**Step 3: Run the focused test to verify RED**

Run:

```bash
cd backend
pytest tests/test_default_workflow_templates_api.py::test_default_runtime_actions_match_prd_state_matrix tests/test_default_workflow_templates_api.py::test_default_runtime_actions_enforce_prd_identity_boundaries -v
```

Expected: FAIL because the default Bug graph still exposes redundant ownership actions on the old initial node and has no edit command.

**Step 4: Confirm failure quality**

The failure must concern the action matrix. If state-role lookup fails, N-002 is incomplete; stop N-004 and finish its prerequisite instead of adding a name-based fallback.

**Step 5: Proposed Git checkpoint**

After delivery approval only:

```bash
git add backend/tests/test_default_workflow_templates_api.py
git commit -m "test: define bug workflow action matrix"
```

### Task 2: Update the default Bug graph on top of N-002

**Files:**
- Modify: `backend/app/services/default_workflow_template_service.py:641-860`
- Test: `backend/tests/test_default_workflow_templates_api.py`

**Step 1: Remove redundant unassigned ownership actions**

In the N-002 version of `_bug_graph()`, keep `claim` and `assign` on the `unassigned` state and remove `_ownership_transition("transfer", ...)` and `_ownership_transition("change_handler", ...)` from that state only.

**Step 2: Add edit commands to the two allowed states**

Add the equivalent of the existing requirement/task command to `unassigned` and `waiting_iteration`:

```python
_command_transition(
    "edit",
    "编辑",
    state_ref,
    allowed_roles="creator",
    command_type="edit",
)
```

Set `ui_config.list_display` to `more` through the established helper/default convention. Do not add edit to `active_work` or any later state.

**Step 3: Preserve ownership actions after assignment**

Verify that `waiting_iteration` and `active_work` still define both `transfer` and management-only `change_handler`, with the N-002 target-state behavior unchanged.

**Step 4: Run the focused tests to verify GREEN**

Run:

```bash
cd backend
pytest tests/test_default_workflow_templates_api.py::test_default_runtime_actions_match_prd_state_matrix tests/test_default_workflow_templates_api.py::test_default_runtime_actions_enforce_prd_identity_boundaries -v
```

Expected: PASS with the new role-based action matrix.

**Step 5: Proposed Git checkpoint**

After delivery approval only:

```bash
git add backend/app/services/default_workflow_template_service.py backend/tests/test_default_workflow_templates_api.py
git commit -m "feat: align default bug workflow actions"
```

### Task 3: Migrate deployed managed Bug workflows idempotently

**Files:**
- Modify: `backend/app/services/default_workflow_template_service.py`
- Create: `backend/alembic/versions/20260822_001_align_bug_workflow_actions.py`
- Create: `backend/tests/test_bug_workflow_action_alignment_migration.py`
- Test: `backend/tests/test_default_workflow_templates_api.py`

**Step 1: Write migration contract tests**

Create source and database-backed tests that require:

- `down_revision = "20260819_008"` unless N-002 adds a later revision; in that case use the actual N-002 head.
- the migration selects only N-002-recognized managed default Bug definitions;
- states are resolved by stable role, never by `status_name`;
- `edit` is upserted for `unassigned` and `waiting_iteration`;
- `transfer/change_handler` are disabled or removed only for `unassigned`;
- `waiting_iteration/active_work` ownership actions remain enabled;
- running reconciliation twice produces one action per `(definition_id, from_state_id, action_key)`;
- a custom definition is unchanged;
- a managed definition missing N-002 roles raises an explicit migration error.

**Step 2: Run the migration test to verify RED**

Run:

```bash
cd backend
pytest tests/test_bug_workflow_action_alignment_migration.py -v
```

Expected: FAIL because the migration and reconciliation helper do not exist.

**Step 3: Implement the reconciliation helper**

Add a focused function such as:

```python
def reconcile_bug_action_matrix(db: Session, definition: WorkflowDefinition) -> None:
    ...
```

Reuse the N-002 managed-definition selector and stable-role resolver. Reuse `_template_role_values()` and `_replace_transition_role_refs()` when creating/updating the creator-only edit command. Preserve administrator-authored actions outside the explicitly managed state/action pairs.

**Step 4: Add the Alembic data migration**

Query the N-002-recognized managed Bug definitions, call `reconcile_bug_action_matrix()` for each, flush, and leave `downgrade()` non-destructive with a clear comment. Do not silently skip a selected definition whose state-role contract is incomplete.

**Step 5: Run migration tests twice**

Run:

```bash
cd backend
pytest tests/test_bug_workflow_action_alignment_migration.py -v
pytest tests/test_bug_workflow_action_alignment_migration.py -v
```

Expected: both runs PASS; the second run proves the test setup and reconciliation remain idempotent.

**Step 6: Run adjacent backend regression tests**

Run:

```bash
cd backend
pytest tests/test_default_workflow_templates_api.py tests/test_workflow_runtime_api.py tests/test_bug_workflow_api.py -v
```

Expected: PASS. Update old assertions that expected transfer/change-handler on the unassigned Bug state, but retain assertions for waiting and active states.

**Step 7: Proposed Git checkpoint**

After delivery approval only:

```bash
git add backend/app/services/default_workflow_template_service.py backend/alembic/versions/20260822_001_align_bug_workflow_actions.py backend/tests/test_bug_workflow_action_alignment_migration.py backend/tests/test_default_workflow_templates_api.py
git commit -m "fix: migrate managed bug workflow actions"
```

### Task 4: Route project-detail Bug editing through the workflow command

**Files:**
- Modify: `frontend/src/views/projectDetailWorkflowIterationLayout.test.mjs:35-55`
- Modify: `frontend/src/views/ProjectDetailView.vue:321-334`
- Modify: `frontend/src/views/ProjectDetailView.vue:1403-1405`
- Read: `frontend/src/views/BugsView.vue:183-191`
- Read: `frontend/src/views/BugDetailView.vue:403-410`

**Step 1: Add failing project-detail contract assertions**

Extract the Bug tab template and assert:

```javascript
assert.doesNotMatch(
  bugsTemplate,
  /@click="openBugEdit\(row\)">编辑<\/el-button>/,
  'bug edit visibility must come from workflow configuration only'
)
assert.match(bugsTemplate, /<WorkflowActionButtons/)
assert.match(bugsTemplate, /@command="handleBugWorkflowCommand\(row, \$event\)"/)
assert.match(
  source,
  /function handleBugWorkflowCommand\(row, \{ commandType \}\) \{\s*if \(commandType === 'edit'\) openBugEdit\(row\)/
)
```

Keep the N-003 task assertions intact so both object types remain workflow-controlled.

**Step 2: Run the test to verify RED**

Run:

```bash
cd frontend
node src/views/projectDetailWorkflowIterationLayout.test.mjs
```

Expected: FAIL because the Bug tab still has a fixed edit button and no command listener.

**Step 3: Implement the command route**

Remove the fixed Bug edit button, add `@command="handleBugWorkflowCommand(row, $event)"` to its `WorkflowActionButtons`, and place this handler beside `openBugEdit`:

```javascript
function handleBugWorkflowCommand(row, { commandType }) {
  if (commandType === 'edit') openBugEdit(row)
}
```

Do not send an edit command to `executeWorkflowTransition`; retain the existing delete button and `@executed` refresh.

**Step 4: Run focused frontend tests**

Run:

```bash
cd frontend
node src/views/projectDetailWorkflowIterationLayout.test.mjs
node src/components/workflowActionButtonsBehavior.test.mjs
node src/utils/workflowRuntimeActions.test.mjs
```

Expected: all three commands PASS.

**Step 5: Proposed Git checkpoint**

After delivery approval only:

```bash
git add frontend/src/views/ProjectDetailView.vue frontend/src/views/projectDetailWorkflowIterationLayout.test.mjs
git commit -m "fix: route project bug editing through workflow"
```

### Task 5: Verify N-004 end to end

**Files:**
- Modify after evidence: `docs/issues/2026-08-22-后续问题清单.md`
- Read: `docs/plans/2026-08-22-bug-workflow-action-alignment-design.md`

**Step 1: Run backend verification**

Run:

```bash
cd backend
pytest tests/test_bug_workflow_action_alignment_migration.py tests/test_default_workflow_templates_api.py tests/test_workflow_runtime_api.py tests/test_bug_workflow_api.py -v
alembic upgrade head
alembic current
```

Expected: all tests PASS; migration reaches the N-004 revision based on the actual N-002 head.

**Step 2: Run frontend verification**

Run:

```bash
cd frontend
npm test
npm run build
```

Expected: full frontend test suite passes and Vite production build exits with code 0.

**Step 3: Perform browser acceptance**

For Bug items in `unassigned`, `waiting_iteration`, and `active_work`, verify all three surfaces: global Bug list, Bug detail, and project-detail Bug tab.

- `unassigned`: “指派” exists; “转派/变更处理人” do not; edit appears only for an allowed creator.
- `waiting_iteration`: edit and the two ownership-transfer actions follow their configured roles and grouping.
- `active_work`: ownership-transfer actions remain; edit is absent.
- Configure edit once as primary and once as more; both open the existing editor.
- Confirm editing sends only the Bug update request and no workflow transition request.
- Confirm an unauthorized identity sees no edit action and cannot obtain edit capability from a fixed page button.

**Step 4: Check formatting and scope**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; only N-004/N-002 implementation files and pre-existing user changes are listed.

**Step 5: Update the issue evidence**

If automated and browser checks pass, change N-004 from `待实施（前置依赖 N-002）` to `待验证` and replace `尚未实施` with exact commands, test counts, migration revision, build result, and browser scenarios. Do not mark it `已解决` before product acceptance.

**Step 6: Request delivery confirmation**

Report the implementation and fresh verification evidence, then ask the required five-option Git delivery question. Perform no Git operation until the user chooses.
