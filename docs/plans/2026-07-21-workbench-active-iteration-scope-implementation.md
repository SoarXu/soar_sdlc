# Workbench Active Iteration Scope Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restrict the workbench to current active-iteration execution, add an unplanned queue, enforce immutable completed iterations, and support audited cross-iteration Bug reactivation with handler retention and reopen counts.

**Architecture:** Reuse dynamic workflow state identity by determining active iterations from their available `complete`/`cancel` transitions rather than display names. Centralize iteration mutability and scope checks in iteration services, add an immutable membership-history table, and extend the existing workflow runtime `reactivate` action for atomic Bug transfer and handler routing. The frontend consumes already-scoped backend sections and supplies dynamic active-iteration and eligible-handler choices to the existing workflow action dialog.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, MySQL/SQLite-compatible schema initialization, Pytest, Vue 3, Element Plus, Node test runner, Vite.

---

### Task 1: Workbench Active-Iteration Scope And Unplanned Queue

**Files:**
- Modify: `backend/app/views/dashboard_view.py`
- Modify: `backend/app/services/dashboard_service.py`
- Modify: `backend/app/services/project_permission_service.py`
- Test: `backend/tests/test_dashboard_workbench_api.py`
- Test: `backend/tests/test_current_handler_assignment_api.py`

**Step 1: Write failing scope tests**

Add tests proving:

- pending and unassigned include only non-terminal items in active iterations;
- planning, terminal-iteration, and uniterated items are excluded from those queues;
- `unplanned` contains only uniterated non-terminal requirement/task/Bug items;
- created/watched/mentioned contain only active-iteration items;
- a user with no visible projects receives no project-scoped queue data;
- system administrators explicitly receive all-project scope;
- every section removes items from projects the actor cannot view.

**Step 2: Run the target tests and verify RED**

Run:

```powershell
python -m pytest backend/tests/test_dashboard_workbench_api.py backend/tests/test_current_handler_assignment_api.py -q
```

Expected: new tests fail because current queries ignore iteration state and the response has no `unplanned` section.

**Step 3: Implement stable active-iteration selection**

Add a helper that identifies active iterations from enabled outgoing `complete` or `cancel` transitions on the iteration's current workflow state. Do not compare `status_name` text.

Build explicit project scope semantics:

```python
all_projects = is_system_admin(db, user_id)
visible_project_ids = None if all_projects else workbench_project_ids_for_user(db, user_id)
```

Use `None` for unrestricted and an empty set for no visible projects. All queue predicates must preserve that distinction.

**Step 4: Implement section predicates**

- `pending_handling`: active iteration, non-terminal, owner is actor, project view allowed.
- `unassigned`: active iteration, non-terminal, no owner, project view allowed.
- `unplanned`: no iteration, non-terminal, project scheduling/view scope allowed.
- tracking sections: active iteration and project view allowed.
- exception center: active iteration exceptions plus separately classified historical integrity exceptions.

**Step 5: Run target tests and verify GREEN**

Run the Step 2 command and expect all tests to pass.

### Task 2: Workbench Frontend Unplanned Experience

**Files:**
- Modify: `frontend/src/utils/workbenchViewModel.js`
- Modify: `frontend/src/utils/workbenchViewModel.test.mjs`
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/utils/workbenchViewModel.test.mjs`

**Step 1: Write failing view-model tests**

Test that:

- entry order is pending, unassigned, unplanned, exception center, following;
- summary cards include unplanned;
- no historical/iteration-status switch is exposed;
- unplanned rows use the existing shared list and workflow actions.

**Step 2: Run the frontend test and verify RED**

```powershell
node frontend/src/utils/workbenchViewModel.test.mjs
```

**Step 3: Implement the view model and page**

Add `unplanned` with label `待规划` and description `未纳入迭代的非终态工作项，等待排期。`. Keep the shared table, keyword/type filters, and active scoped backend payload. Update empty-state copy to mention the current section scope.

**Step 4: Run frontend tests and verify GREEN**

```powershell
npm --prefix frontend test
```

### Task 3: Iteration Terminal Gate Details And Write Protection

**Files:**
- Modify: `backend/app/services/iteration_service.py`
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/controllers/iteration_controller.py`
- Modify: `backend/app/views/iteration_view.py`
- Test: `backend/tests/test_iteration_detail_api.py`
- Test: `backend/tests/test_workflow_runtime_api.py`

**Step 1: Write failing gate and mutation tests**

Cover:

- terminal iterations reject patch, link, unlink, defer-source and ordinary move operations;
- active/planning iterations retain allowed mutations;
- terminal-gate failure returns `ITERATION_HAS_OPEN_ITEMS`, counts by object type, and item summaries;
- failed gate leaves iteration state unchanged;
- complete/cancel still succeeds when all direct work items and test runs are terminal.

**Step 2: Verify RED**

```powershell
python -m pytest backend/tests/test_iteration_detail_api.py backend/tests/test_workflow_runtime_api.py -q
```

**Step 3: Add centralized guards**

Implement helpers:

```python
def ensure_iteration_mutable(db: Session, iteration: Iteration) -> None: ...
def iteration_blockers(db: Session, iteration_id: int) -> dict[str, list[dict]]: ...
```

Terminal identity uses state category. The guard returns HTTP 409 with a stable detail object containing `code="ITERATION_NOT_MUTABLE"`.

**Step 4: Return structured gate errors**

`ensure_iteration_items_complete` raises HTTP 400 with:

```json
{
  "code": "ITERATION_HAS_OPEN_ITEMS",
  "message": "存在未完成事项，无法结束迭代",
  "counts": {"requirement": 1, "task": 0, "bug": 1, "test_run": 0},
  "items": [{"object_type": "requirement", "id": 1, "title": "...", "status_name": "...", "owner_id": 2}]
}
```

**Step 5: Verify GREEN**

Run the Step 2 command.

### Task 4: Iteration Membership History

**Files:**
- Create: `backend/app/models/work_item_iteration_history.py`
- Create: `backend/app/services/work_item_iteration_history_service.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/db/schema.py`
- Modify: `backend/app/services/iteration_service.py`
- Modify: `docs/database/init_mysql.sql`
- Test: `backend/tests/test_work_item_iteration_history.py`
- Test: `backend/tests/test_model_metadata.py`

**Step 1: Write failing model and service tests**

Test initial link, unlink, defer, idempotent current membership, and immutable closed history. Verify one open history row matches the current `iteration_id`.

**Step 2: Verify RED**

```powershell
python -m pytest backend/tests/test_work_item_iteration_history.py backend/tests/test_model_metadata.py -q
```

**Step 3: Add model and runtime schema**

Create `work_item_iteration_history` with object type/id, iteration id, entered/left timestamps and actors, enter/leave reasons, operation-log id, migration flag, and indexes on object and iteration. Add MySQL bootstrap DDL and SQLAlchemy metadata.

**Step 4: Record all iteration mutations**

Centralize assignment in:

```python
def move_work_item_to_iteration(db, item, target_iteration_id, actor_id, reason, operation_log_id=None): ...
```

Use it from link, unlink and defer paths. Do not update `iteration_id` directly in those paths.

**Step 5: Add safe initialization**

Backfill current memberships only when no history exists, marking rows as migration-derived. Do not invent historical timestamps.

**Step 6: Verify GREEN**

Run the Step 2 command and the iteration-detail tests.

### Task 5: Atomic Cross-Iteration Bug Reactivation

**Files:**
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/services/default_workflow_template_service.py`
- Modify: `backend/app/services/iteration_service.py`
- Modify: `backend/app/services/work_item_iteration_history_service.py`
- Modify: `backend/app/views/workflow_runtime_view.py`
- Test: `backend/tests/test_bug_workflow_api.py`
- Test: `backend/tests/test_workflow_runtime_api.py`
- Test: `backend/tests/test_default_workflow_templates_api.py`

**Step 1: Write failing reactivation tests**

Cover:

- active-iteration Bug reactivates in place and increments `reopen_count`;
- terminal-iteration Bug requires active target iteration and reason;
- planning/terminal/out-of-project targets are rejected with stable error codes;
- Bug ID remains unchanged and target iteration becomes current;
- valid active project-member original handler is retained by default;
- inactive, deleted, removed, or ineligible original handler is not retained;
- authorized manual handler override succeeds and is audited;
- unassigned is accepted only when workflow configuration permits it;
- repeat/concurrent requests do not double-increment or leave partial history.

**Step 2: Verify RED**

```powershell
python -m pytest backend/tests/test_bug_workflow_api.py backend/tests/test_workflow_runtime_api.py backend/tests/test_default_workflow_templates_api.py -q
```

**Step 3: Extend the default reactivation form**

Keep `reactivate` as the action key. Add dynamic target-iteration metadata, reason, and manual-owner support to its form/UI configuration. Configure `keep_current` as the default handler source and allow unassigned only when explicitly enabled.

**Step 4: Implement domain validation before mutation**

For terminal source iterations require `payload.target_iteration_id`; identify active target state from workflow transitions; validate project scope; evaluate original handler activity, project membership and workflow eligibility; store recommendation and override metadata in `selected_values`.

**Step 5: Apply one atomic transition**

Within the existing workflow transaction:

- close source membership history;
- open target membership history;
- update Bug `iteration_id`;
- increment `reopen_count` once;
- resolve final owner;
- update workflow state;
- create status-operation audit with source/target iteration and owner-decision metadata.

**Step 6: Verify GREEN**

Run Step 2 and iteration-history tests.

### Task 6: Bug Reactivation Frontend

**Files:**
- Modify: `frontend/src/components/WorkflowActionButtons.vue`
- Modify: `frontend/src/views/BugDetailView.vue`
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/api/iterations.js`
- Modify: `frontend/src/utils/workflowRuntimeActions.js`
- Test: `frontend/src/components/workflowActionButtonsBehavior.test.mjs`
- Test: `frontend/src/utils/workflowRuntimeActions.test.mjs`

**Step 1: Write failing component/source-contract tests**

Verify active-iteration option sources, original-handler recommendation, required reason, manual override, and disabled submit when no active target exists.

**Step 2: Verify RED**

```powershell
npm --prefix frontend test
```

**Step 3: Implement dynamic form context**

Allow `WorkflowActionButtons` to receive active iterations and eligible users. Bind target iteration to `payload.target_iteration_id`, bind owner selection to `next_owner_id`, and show recommendation/unavailability text without duplicating transition execution logic.

**Step 4: Load options in Bug detail and workbench**

Fetch iterations visible for the Bug project, retain only active iteration identities, and pass them with project members to the action component. Do not offer planning or terminal targets.

**Step 5: Verify GREEN and build**

```powershell
npm --prefix frontend test
npm --prefix frontend run build
```

### Task 7: Historical Integrity Exceptions And Regression Coverage

**Files:**
- Modify: `backend/app/services/exception_center_service.py`
- Modify: `backend/app/services/dashboard_service.py`
- Test: `backend/tests/test_exception_center_api.py`
- Test: `backend/tests/test_dashboard_workbench_api.py`
- Modify: `frontend/src/utils/workbenchViewModel.js`

**Step 1: Write failing integrity-exception tests**

Test terminal iterations containing non-terminal work items and membership-history conflicts. Verify normal terminal snapshots do not enter the exception center and permissions remain enforced.

**Step 2: Verify RED**

```powershell
python -m pytest backend/tests/test_exception_center_api.py backend/tests/test_dashboard_workbench_api.py -q
```

**Step 3: Implement integrity refs**

Add explicit exception keys such as `terminal_iteration_open_item` and `iteration_membership_conflict`. These do not depend on normal timeout thresholds and include source/current iteration metadata.

**Step 4: Verify GREEN**

Run Step 2.

### Task 8: Full Verification And Visual QA

**Files:**
- Verify all modified files.

**Step 1: Run full backend tests**

```powershell
python -m pytest backend/tests -q
```

Expected: all tests pass.

**Step 2: Run frontend tests and build**

```powershell
npm --prefix frontend test
npm --prefix frontend run build
```

Expected: tests and production build pass.

**Step 3: Run repository hygiene checks**

```powershell
git diff --check
git status --short
```

**Step 4: Start the application and perform desktop visual QA**

Verify the workbench entry order, active-only data, unplanned empty/data states, iteration completion blocker dialog, and Bug reactivation form at the project fixed desktop viewport. Capture screenshots if browser tooling is available.

**Step 5: Review against PRD acceptance criteria**

Check AC1-AC12 line by line and record any deliberate deferral. Do not claim PRD completion with an unverified acceptance criterion.
