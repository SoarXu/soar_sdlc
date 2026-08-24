# Task Hierarchy Consistency Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add arbitrary-depth child tasks while keeping each task tree aligned with its requirement, project, iteration, N-002 state, and terminal-state rules.

**Architecture:** Store the direct parent on `tasks`, centralize traversal and aggregate validation in a task hierarchy service, and make requirement/root-task moves operate on a locked task tree in one transaction. Add a workflow terminal gate for unfinished descendants and expose direct children in the task detail UI without changing flat list pagination.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, Alembic, pytest, Vue 3, Element Plus, JavaScript source-contract tests, Vite.

---

## Execution Rules

- Prerequisite: N-002 must be implemented and verified. Reuse its stable state roles and iteration-move workflow service; do not assign `current_state_id` directly.
- Use @test-driven-development for every production change.
- Use @systematic-debugging when a failure is not the expected RED result.
- Use @verification-before-completion before updating N-005 or claiming success.
- Work in the current workspace because the issue and design documents already exist here.
- Do not commit, push, merge, or create a PR until the repository delivery confirmation is answered. Commit commands below are proposed checkpoints only.
- Preserve unrelated changes in `issue.md`, `deploy/`, `deploy.tar.gz`, and other 2026-08-22 documents.

### Task 1: Add the task parent relation and migration contract

**Files:**
- Create: `backend/alembic/versions/20260822_002_task_hierarchy.py`
- Create: `backend/tests/test_task_hierarchy_migration.py`
- Modify: `backend/app/models/task.py:8-50`
- Modify: `backend/app/views/task_view.py:9-110`

**Step 1: Write the failing model and migration tests**

Require the ORM and schema to expose a nullable indexed self-reference:

```python
assert Task.__table__.c.parent_task_id.nullable is True
assert Task.__table__.c.parent_task_id.foreign_keys
assert "parent_task_id" in TaskCreate.model_fields
assert "parent_task_id" not in TaskUpdate.model_fields
assert "parent_task_id" in TaskRead.model_fields
```

The migration source test must require an index, `tasks.id` foreign key with `RESTRICT`, and a self-parent check. Existing rows must remain roots.

**Step 2: Run the tests to verify RED**

Run:

```bash
cd backend
pytest tests/test_task_hierarchy_migration.py -v
```

Expected: FAIL because `parent_task_id` and the migration do not exist.

**Step 3: Implement the model and API fields**

Add to `Task`:

```python
parent_task_id: Mapped[int | None] = mapped_column(
    BigInteger,
    ForeignKey("tasks.id", ondelete="RESTRICT"),
    nullable=True,
    index=True,
)
```

Add `parent_task_id` to `TaskCreate` and `TaskRead`, but not `TaskUpdate`. Add read-only parent summary and `direct_child_count` fields with defaults so old response construction remains compatible.

**Step 4: Implement the migration**

Create the nullable column first, then the index, foreign key, and `parent_task_id IS NULL OR parent_task_id <> id` check. Set `down_revision` to the actual N-002 migration head if it differs from the planned value. Downgrade drops constraints and index before the column.

**Step 5: Run migration tests to verify GREEN**

Run:

```bash
cd backend
pytest tests/test_task_hierarchy_migration.py -v
```

Expected: PASS.

**Step 6: Proposed Git checkpoint**

After delivery approval only:

```bash
git add backend/alembic/versions/20260822_002_task_hierarchy.py backend/tests/test_task_hierarchy_migration.py backend/app/models/task.py backend/app/views/task_view.py
git commit -m "feat: add task parent relation"
```

### Task 2: Centralize task-tree traversal and invariant validation

**Files:**
- Create: `backend/app/services/task_hierarchy_service.py`
- Create: `backend/tests/test_task_hierarchy_service.py`
- Modify: `backend/app/services/task_service.py:65-320`

**Step 1: Write failing hierarchy service tests**

Cover direct children, arbitrary-depth descendants, deleted-node exclusion, stable ordering, self-parent rejection, terminal-parent rejection, and mismatch rejection. Define focused APIs:

```python
def list_direct_children(db: Session, task_id: int) -> list[Task]: ...
def list_descendants(db: Session, task_id: int, *, for_update: bool = False) -> list[Task]: ...
def task_tree(db: Session, root: Task, *, for_update: bool = False) -> list[Task]: ...
def validate_child_parent(parent: Task) -> None: ...
```

**Step 2: Run the service tests to verify RED**

Run:

```bash
cd backend
pytest tests/test_task_hierarchy_service.py -v
```

Expected: FAIL because the service module does not exist.

**Step 3: Implement traversal**

Use a recursive CTE supported by the repository database targets, with a visited/cycle guard in the returned IDs. Filter `deleted == 0`, return deterministic depth/id order, and apply row locking when called for aggregate mutation.

**Step 4: Implement child creation authority**

In `create_task()`, when `parent_task_id` is present:

```python
parent = get_locked_active_task(db, parent_task_id)
validate_child_parent(parent)
data["project_id"] = parent.project_id
data["requirement_id"] = parent.requirement_id
data["iteration_id"] = parent.iteration_id
```

Reject terminal or deleted parents. Initialize the child's workflow status through N-002 using the inherited iteration and selected owner.

**Step 5: Attach hierarchy read metadata**

Extend `get_task()` to attach the parent summary and direct child count without recursively embedding children. Keep list endpoints free from N+1 queries by using aggregate counts only where the UI consumes them.

**Step 6: Run focused API and service tests**

Run:

```bash
cd backend
pytest tests/test_task_hierarchy_service.py tests/test_requirement_task_api.py -v
```

Expected: PASS, including existing root-task creation tests.

**Step 7: Proposed Git checkpoint**

After delivery approval only:

```bash
git add backend/app/services/task_hierarchy_service.py backend/tests/test_task_hierarchy_service.py backend/app/services/task_service.py
git commit -m "feat: enforce task hierarchy invariants"
```

### Task 3: Expose direct children and enforce permissions

**Files:**
- Modify: `backend/app/controllers/task_controller.py:28-100`
- Modify: `backend/app/services/task_service.py`
- Create: `backend/tests/test_task_hierarchy_api.py`
- Modify: `frontend/src/api/tasks.js`

**Step 1: Write failing API tests**

Cover:

- authenticated project member creates a child under a visible parent;
- child ignores spoofed project/requirement/iteration values and inherits the parent;
- non-member cannot create or list children;
- terminal parent rejects child creation with structured `409`;
- `GET /tasks/{id}/children` returns direct children only and paginates;
- `TaskRead` exposes parent summary and direct child count;
- attempting to send `parent_task_id` in PATCH is rejected as an extra field.

**Step 2: Run the API tests to verify RED**

Run:

```bash
cd backend
pytest tests/test_task_hierarchy_api.py -v
```

Expected: FAIL because the child endpoint and hierarchy behavior do not exist.

**Step 3: Add the child-list endpoint**

Add `GET /tasks/{task_id}/children` with the same project visibility boundary as task detail. Return the repository's standard paginated task response shape.

**Step 4: Add frontend API helpers**

Add `fetchTaskChildren(taskId, params)` and continue using `createTask()` with `parent_task_id` for creation. Do not introduce a second creation protocol.

**Step 5: Run the focused tests to verify GREEN**

Run:

```bash
cd backend
pytest tests/test_task_hierarchy_api.py tests/test_linked_task_api.py -v
```

Expected: PASS.

**Step 6: Proposed Git checkpoint**

After delivery approval only:

```bash
git add backend/app/controllers/task_controller.py backend/app/services/task_service.py backend/tests/test_task_hierarchy_api.py frontend/src/api/tasks.js
git commit -m "feat: expose task children API"
```

### Task 4: Move requirement and task aggregates atomically

**Files:**
- Modify: `backend/app/services/task_hierarchy_service.py`
- Modify: `backend/app/services/work_item_iteration_history_service.py:22-115`
- Modify: `backend/app/services/requirement_service.py:86-140`
- Modify: `backend/app/services/task_service.py:240-285`
- Modify: `backend/app/services/iteration_service.py:300-430`
- Modify: `backend/tests/test_requirement_real_iteration_assignment_api.py`
- Modify: `backend/tests/test_work_item_iteration_history.py`
- Create: `backend/tests/test_task_tree_iteration_move.py`

**Step 1: Write failing aggregate movement tests**

Build a requirement with two root tasks and grandchildren. Assert that moving the requirement updates every task's project, requirement, and iteration, writes one history entry per moved task, and applies N-002 status transitions. Add independent root-task tree movement and child-direct-move rejection.

Add rollback cases where one descendant is terminal, has an incompatible N-002 state, or fails target project permission. After failure, assert every requirement/task row and history count is unchanged.

**Step 2: Run the movement tests to verify RED**

Run:

```bash
cd backend
pytest tests/test_task_tree_iteration_move.py tests/test_requirement_real_iteration_assignment_api.py -v
```

Expected: FAIL because only direct tasks are currently synchronized.

**Step 3: Implement preflight and atomic movement**

Add an aggregate operation that locks the requirement/root and all descendant tasks, validates the complete target state, then invokes the N-002 move service for each item. Do not commit inside per-item helpers; the caller owns the transaction.

**Step 4: Enforce root-only ownership changes**

In `update_task()`, reject project, requirement, or iteration changes for child tasks with:

```json
{
  "code": "CHILD_TASK_SCOPE_IMMUTABLE",
  "message": "子任务的项目、需求和迭代由父任务统一管理。"
}
```

For a root task, cascade any accepted change to the whole tree. If linked to a requirement, require exact project/iteration equality with that requirement.

**Step 5: Replace direct requirement-dependent movement**

Update `move_requirement_dependents_to_iteration()` and all requirement/iteration entry points to collect complete task trees. Preserve unrelated Bugs and standalone tasks under their existing rules.

**Step 6: Run movement regressions**

Run:

```bash
cd backend
pytest tests/test_task_tree_iteration_move.py tests/test_requirement_real_iteration_assignment_api.py tests/test_work_item_iteration_history.py tests/test_iteration_detail_api.py -v
```

Expected: PASS with no partial movement or direct-child escape.

**Step 7: Proposed Git checkpoint**

After delivery approval only:

```bash
git add backend/app/services/task_hierarchy_service.py backend/app/services/work_item_iteration_history_service.py backend/app/services/requirement_service.py backend/app/services/task_service.py backend/app/services/iteration_service.py backend/tests/test_task_tree_iteration_move.py backend/tests/test_requirement_real_iteration_assignment_api.py backend/tests/test_work_item_iteration_history.py
git commit -m "feat: move requirement task trees atomically"
```

### Task 5: Block task terminal transitions on open descendants

**Files:**
- Modify: `backend/app/services/workflow_runtime_service.py:1685-1705`
- Modify: `backend/app/services/default_workflow_template_service.py:470-635`
- Create: `backend/tests/test_task_descendant_terminal_gate.py`
- Create: `backend/alembic/versions/20260822_003_task_descendant_terminal_gate.py`
- Create: `backend/tests/test_task_descendant_terminal_gate_migration.py`

**Step 1: Write failing terminal-gate tests**

Cover direct and deep open descendants for both completion and cancellation. Verify completed/canceled descendants allow the transition, deleted descendants are ignored, leaves pass, and rejection returns `TASK_DESCENDANTS_NOT_TERMINAL` with id, title, status, and parent ID.

Cover task types that complete directly and task types that reach completion after confirmation; assert the gate runs on the transition entering the terminal state, not on `submit_confirmation`.

**Step 2: Run the gate tests to verify RED**

Run:

```bash
cd backend
pytest tests/test_task_descendant_terminal_gate.py -v
```

Expected: FAIL because the task descendant validator is unsupported.

**Step 3: Implement the validator**

Register `task_descendants_terminal_gate` in `_run_transition_validators()`. Resolve descendant terminal semantics through stable state metadata, not Chinese names. Raise one structured `409` containing all non-terminal descendants.

**Step 4: Update defaults and deployed managed definitions**

Add the validator to every default task transition whose resolved target is completed or canceled. Add an idempotent data migration for recognized managed default task workflows; preserve custom definitions and use the actual migration head.

**Step 5: Run focused and migration tests**

Run:

```bash
cd backend
pytest tests/test_task_descendant_terminal_gate.py tests/test_task_descendant_terminal_gate_migration.py tests/test_default_workflow_templates_api.py tests/test_workflow_runtime_api.py -v
```

Expected: PASS and no duplicate validator configuration after repeated reconciliation.

**Step 6: Proposed Git checkpoint**

After delivery approval only:

```bash
git add backend/app/services/workflow_runtime_service.py backend/app/services/default_workflow_template_service.py backend/tests/test_task_descendant_terminal_gate.py backend/alembic/versions/20260822_003_task_descendant_terminal_gate.py backend/tests/test_task_descendant_terminal_gate_migration.py
git commit -m "feat: block terminal tasks with open descendants"
```

### Task 6: Add the task-detail child workflow

**Files:**
- Modify: `frontend/src/views/TaskDetailView.vue:1-310`
- Modify: `frontend/src/api/tasks.js`
- Create: `frontend/src/views/taskHierarchy.test.mjs`
- Modify: `frontend/src/components/WorkflowActionButtons.vue`
- Modify: `frontend/src/components/workflowActionButtonsBehavior.test.mjs`

**Step 1: Write failing frontend contract tests**

Require Task detail to show a parent link, a direct-child table, a permission-gated “新增子任务” action, inherited read-only scope fields, and child links. Require `WorkflowActionButtons` to recognize `TASK_DESCENDANTS_NOT_TERMINAL` and render blocker rows.

**Step 2: Run tests to verify RED**

Run:

```bash
cd frontend
node src/views/taskHierarchy.test.mjs
node src/components/workflowActionButtonsBehavior.test.mjs
```

Expected: FAIL on missing child UI and blocker support.

**Step 3: Implement the task-detail section**

Load direct children alongside task detail. Add a compact unframed section with title, owner, status, iteration, and detail link. Keep stable column widths and paginate when the child count exceeds the page size.

**Step 4: Implement child creation**

Reuse the existing task form fields, submit `parent_task_id`, and show inherited project/requirement/iteration as read-only values. On success, close the dialog and reload task metadata plus the child list.

**Step 5: Implement structured blocker display**

Map `TASK_DESCENDANTS_NOT_TERMINAL` into the existing blocker dialog and route each row to `/tasks/{id}`. Do not reduce the response to a toast because users need to locate every blocker.

**Step 6: Run focused tests and build**

Run:

```bash
cd frontend
node src/views/taskHierarchy.test.mjs
node src/components/workflowActionButtonsBehavior.test.mjs
npm run build
```

Expected: focused tests PASS and Vite exits with code 0.

**Step 7: Proposed Git checkpoint**

After delivery approval only:

```bash
git add frontend/src/views/TaskDetailView.vue frontend/src/api/tasks.js frontend/src/views/taskHierarchy.test.mjs frontend/src/components/WorkflowActionButtons.vue frontend/src/components/workflowActionButtonsBehavior.test.mjs
git commit -m "feat: add task detail child workflow"
```

### Task 7: Execute the N-005 validation plan

**Files:**
- Read: `docs/plans/2026-08-22-task-hierarchy-consistency-validation.md`
- Modify after evidence: `docs/issues/2026-08-22-后续问题清单.md`

**Step 1: Run every automated check in the validation plan**

Execute migration, hierarchy, aggregate movement, terminal gate, backend regression, frontend tests, and production build exactly as listed in the validation document.

**Step 2: Perform browser acceptance**

Verify three-level creation, inherited scope, requirement and independent-root moves, N-002 state changes, direct-child move rejection, terminal blocking, blocker navigation, and successful completion after all descendants become terminal.

**Step 3: Update N-005 with evidence**

If all required checks pass, change N-005 to `待验证` and record exact commands, test counts, Alembic revisions, build output, and browser scenarios. Do not mark it `已解决` before product acceptance.

**Step 4: Request delivery confirmation**

Report implementation and fresh verification evidence, then ask the required five-option Git delivery question. Perform no Git operation until the user chooses.
