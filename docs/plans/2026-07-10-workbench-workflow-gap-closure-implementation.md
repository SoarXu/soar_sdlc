# Workbench Workflow Gap Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Close G1-G14 from the 2026-07-10 workbench/workflow gap-closure PRD so the default workflow is usable, permission-safe, auditable, and consistently rendered across backend and frontend.

**Architecture:** Keep FastAPI, SQLAlchemy, Vue 3, Element Plus, and the existing workflow-definition/runtime model. Make workflow runtime the only authority for status and handler changes, use structured persisted data for Bug types and exception thresholds, use `object_relation` for multi-source linked tasks, and migrate all active UI code to canonical statuses without a long-lived compatibility layer. Work in the current main workspace as explicitly requested; preserve unrelated user changes and do not create a worktree or commit unless requested.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy, Alembic, Pytest, Vue 3, Element Plus, Node test runner, Vite.

---

## Execution Rules

- Execute tasks in order because schema, runtime, domain services, and UI have dependencies.
- Use `superpowers:test-driven-development` for every behavior change.
- Use `superpowers:systematic-debugging` for any unexpected failure.
- After each task, run only its focused tests, report the completed function, completion status, and manual verification path.
- Run the broader backend and frontend verification after Tasks 5, 8, and 10.
- Do not run mobile or moving-viewport checks; use the fixed desktop viewport only for final UI verification.
- Do not delete unrelated dirty-worktree changes. Delete legacy workflow code only after references and tests prove it is unused.

### Task 1: Canonical Task Branches And Creation Invariants (G1)

**Files:**
- Modify: `backend/app/views/task_view.py`
- Modify: `backend/app/views/requirement_view.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/services/requirement_service.py`
- Modify: `backend/app/controllers/task_controller.py`
- Modify: `frontend/src/views/TasksView.vue`
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/views/RequirementDetailView.vue`
- Modify: `frontend/src/views/RequirementsView.vue`
- Modify: `frontend/src/views/TaskDetailView.vue`
- Test: `backend/tests/test_requirement_task_api.py`
- Test: `backend/tests/test_default_workflow_templates_api.py`
- Test: `frontend/src/utils/taskBranchRules.test.mjs`
- Create: `frontend/src/utils/taskBranchRules.js`

**Step 1: Write failing backend tests**

- Creating a standalone task without `task_type` stores `standalone_operation`.
- Creating a task with `requirement_id` derives `requirement_implementation`.
- Requirement generate-task derives `requirement_implementation` even when omitted.
- Invalid task types return 422.
- A created task in `In Processing` always has either Complete or Submit Confirmation.

**Step 2: Run tests and confirm failure**

Run: `pytest -q backend/tests/test_requirement_task_api.py backend/tests/test_default_workflow_templates_api.py`

Expected: new branch derivation and validation assertions fail.

**Step 3: Implement backend derivation and validation**

- Define one canonical task-type set.
- Derive type from source before constructing `Task`.
- Reject source/type combinations that contradict each other.
- Prevent clients from creating tasks directly in arbitrary workflow states.
- Set `creator_id` from the authenticated actor while changing the service signature.

**Step 4: Write frontend branch-rule tests**

- Requirement source locks branch to requirement implementation.
- No source defaults to standalone operation.
- All four labels map to stable backend keys.

**Step 5: Implement frontend fields and derivation**

- Add task branch selection to every create/edit surface.
- Display task branch on detail and lists where practical.
- Requirement generate-task submits `requirement_implementation` explicitly.

**Step 6: Verify Task 1**

Run:

```powershell
pytest -q backend/tests/test_requirement_task_api.py backend/tests/test_default_workflow_templates_api.py
Set-Location frontend; npm test -- taskBranchRules; npm run build
```

Expected: focused backend tests, frontend branch tests, and build pass.

### Task 2: Bug Type Dictionary And Routing Form (G2, G8 Partial)

**Files:**
- Create: `backend/app/models/bug_type.py`
- Create: `backend/app/views/bug_type_view.py`
- Create: `backend/app/services/bug_type_service.py`
- Create: `backend/app/controllers/bug_type_controller.py`
- Create: `backend/alembic/versions/20260710_001_bug_type_dictionary.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/controllers/router.py`
- Modify: `backend/app/services/default_workflow_template_service.py`
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `frontend/src/api/bugTypes.js`
- Modify: `frontend/src/components/WorkflowActionButtons.vue`
- Modify: Bug creation/edit views containing local `bugTypeOptions`
- Test: `backend/tests/test_bug_type_api.py`
- Test: `backend/tests/test_workflow_runtime_api.py`
- Test: `frontend/src/utils/workflowRuntimeActions.test.mjs`

**Step 1: Write failing dictionary and routing tests**

- Default dictionary contains all nine PRD types with stable keys.
- Each type exposes `is_real_bug` and `default_target_status`.
- Disabled values are not returned for new selection.
- Confirm Bug Type action returns populated form options.
- Chinese display labels submit stable dictionary keys.

**Step 2: Run tests and confirm failure**

Run: `pytest -q backend/tests/test_bug_type_api.py backend/tests/test_workflow_runtime_api.py`

Expected: missing table/API/options failures.

**Step 3: Implement structured dictionary and seed**

- Add model, migration, CRUD/list service, and router.
- Seed the nine default rows idempotently.
- Make runtime enrich Bug type select fields from the dictionary.
- Validate selected type server-side.

**Step 4: Replace hard-coded frontend options**

- Add one API/composable source for Bug types.
- Replace local arrays in Bugs, Bug detail, dashboard, project, iteration, requirement, and test views.
- Preserve historical disabled labels in display-only contexts.

**Step 5: Verify Task 2**

Run:

```powershell
pytest -q backend/tests/test_bug_type_api.py backend/tests/test_workflow_runtime_api.py backend/tests/test_bug_workflow_api.py
Set-Location frontend; npm test -- workflowRuntimeActions; npm run build
```

Expected: dictionary, runtime routing, frontend tests, and build pass.

### Task 3: Workflow Permission Authority And Ownership Actions (G3, G6 Partial)

**Files:**
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/services/project_permission_service.py`
- Modify: `backend/app/services/work_item_service.py`
- Modify: `backend/app/services/assignment_service.py`
- Modify: `backend/app/services/default_workflow_template_service.py`
- Modify: `backend/app/controllers/work_item_controller.py`
- Modify: requirement/task/bug controllers exposing legacy assign APIs
- Modify: frontend APIs and call sites using legacy Claim/Assign
- Test: `backend/tests/test_workflow_runtime_api.py`
- Test: `backend/tests/test_project_permission_boundary_api.py`
- Test: `backend/tests/test_unassigned_work_items_api.py`
- Test: `backend/tests/test_current_handler_assignment_api.py`

**Step 1: Write failing permission matrix tests**

- Non-project users cannot list or execute Claim/Cancel on ownerless items.
- Project members can Claim when enabled.
- Only project owner/system admin can Assign or Change Handler by default.
- System admin does not need a project-member role row.
- A scoped workflow with no enabled transition does not fall back to the system action.
- Generic edit cannot change owner/status.

**Step 2: Run tests and confirm failure**

Run: `pytest -q backend/tests/test_workflow_runtime_api.py backend/tests/test_project_permission_boundary_api.py backend/tests/test_unassigned_work_items_api.py`

Expected: ownerless membership, system-admin, and fallback tests fail.

**Step 3: Implement identity-aware runtime authorization**

- Add explicit actor identity evaluation: member, creator, reporter, tester, current handler, project owner, system admin.
- Require project membership for ordinary ownerless actions.
- Merge global and project roles for allowed-role checks.
- Make scoped workflow selection authoritative per object.

**Step 4: Unify ownership actions**

- Represent Claim, Assign, Transfer, Change Handler, Transfer Verification, and Transfer Confirmation as runtime actions.
- Record before/after owner, actor, rule, and reason.
- Update owner and status atomically.
- Remove owner changes from ordinary PATCH payload processing.

**Step 5: Remove proven legacy routes and call sites**

- Search for all fixed Claim/Assign endpoints.
- Migrate frontend callers to workflow runtime.
- Delete only routes/services with no remaining references.

**Step 6: Verify Task 3**

Run: `pytest -q backend/tests/test_workflow_runtime_api.py backend/tests/test_project_permission_boundary_api.py backend/tests/test_unassigned_work_items_api.py backend/tests/test_current_handler_assignment_api.py`

Expected: full permission matrix passes.

### Task 4: Previous Handler And Configurable Confirmation Routing (G4)

**Files:**
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/services/default_workflow_template_service.py`
- Modify: `backend/app/services/handler_transition_rule_service.py`
- Modify: `backend/app/models/status_operation.py` only if current structured fields are insufficient
- Create migration only if a new audit column is required
- Test: `backend/tests/test_workflow_runtime_api.py`
- Test: `backend/tests/test_current_handler_assignment_api.py`
- Test: `backend/tests/test_requirement_task_api.py`

**Step 1: Write failing handler-routing tests**

- Bug from test execution resolves repair owner and verifier in PRD order.
- Non-Bug routing to Pending Verification changes owner to verifier.
- Submit Verification changes owner to test executor/default tester/reporter fallback.
- Task branch confirmation resolves the correct source owner.
- Return Rework and Verification Failed restore the persisted execution/repair owner.
- Missing confirmer blocks Pending Confirmation.

**Step 2: Run tests and confirm failure**

Run: `pytest -q backend/tests/test_workflow_runtime_api.py backend/tests/test_current_handler_assignment_api.py backend/tests/test_requirement_task_api.py`

Expected: source-aware routing and true previous-handler assertions fail.

**Step 3: Implement handler source resolvers**

- Resolve creator, source owner, requirement owner, Bug reporter/verifier, test executor/default tester, project owner, fixed user, and fixed role.
- Evaluate ordered fallback chains.
- Read prior owner from status operation history instead of returning current owner.

**Step 4: Add audit metadata and null guard**

- Persist source rule, resolved default, final owner, override flag, and reason.
- Block entry to Pending Confirmation when no owner resolves unless explicitly configured otherwise.

**Step 5: Verify Task 4**

Run: `pytest -q backend/tests/test_workflow_runtime_api.py backend/tests/test_current_handler_assignment_api.py backend/tests/test_requirement_task_api.py`

Expected: handler routing and return tests pass.

### Task 5: Generic Linked Tasks And Multi-Task Bug Gate (G5, G9)

**Files:**
- Modify: `backend/app/models/relation.py`
- Modify: `backend/app/views/task_view.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/controllers/task_controller.py`
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `frontend/src/api/tasks.js`
- Modify: `frontend/src/views/BugDetailView.vue`
- Modify: `frontend/src/views/TaskDetailView.vue`
- Modify: relevant test/requirement detail views
- Test: `backend/tests/test_linked_task_api.py`
- Test: `backend/tests/test_default_workflow_templates_api.py`
- Test: `backend/tests/test_bug_workflow_api.py`

**Step 1: Write failing linked-task tests**

- Create linked tasks from requirement, Bug, test case, and test run.
- Enforce current handler/project owner/system admin creation permission.
- Inherit source handler by default and enter Pending Assignment when absent.
- Record source, creator identity, inherited owner, selected owner, override, and reason.
- One Bug can link multiple tasks.
- Bug close blocks if any linked task is unfinished.

**Step 2: Run tests and confirm failure**

Run: `pytest -q backend/tests/test_linked_task_api.py backend/tests/test_default_workflow_templates_api.py backend/tests/test_bug_workflow_api.py`

Expected: generic source and multi-task gate tests fail.

**Step 3: Implement relation-backed linked task creation**

- Use `ObjectRelation` with normalized source/target types and `linked_task` relation type.
- Add one authenticated endpoint receiving source type/id and task fields.
- Derive project, branch, and owner from source.
- Add relation reads to task and source-object detail APIs.

**Step 4: Replace the single-task Bug gate**

- Resolve all direct linked tasks, including migrated legacy `bug.task_id` during the migration window.
- Return practical blocker IDs/titles/count without mutating tasks.
- Remove single-task-only logic once migration and references are complete.

**Step 5: Add frontend creation and relation display**

- Add Create Linked Task to permitted source details.
- Show source on task detail and all tasks on Bug detail.

**Step 6: Verify Slice A**

Run:

```powershell
pytest -q backend/tests/test_linked_task_api.py backend/tests/test_default_workflow_templates_api.py backend/tests/test_bug_workflow_api.py backend/tests/test_requirement_task_api.py backend/tests/test_workflow_runtime_api.py backend/tests/test_current_handler_assignment_api.py
Set-Location frontend; npm test; npm run build
```

Expected: Tasks 1-5 pass together.

### Task 6: Complete Default Action Matrices And Reactivation (G6, G7, G8)

**Files:**
- Modify: `backend/app/services/default_workflow_template_service.py`
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/views/workflow_runtime_view.py`
- Modify: `frontend/src/components/WorkflowActionButtons.vue`
- Modify: requirement/task/bug detail and list views
- Test: `backend/tests/test_default_workflow_templates_api.py`
- Test: `backend/tests/test_workflow_runtime_api.py`
- Test: `backend/tests/test_bug_workflow_api.py`
- Test: `frontend/src/utils/workflowRuntimeActions.test.mjs`

**Step 1: Write failing action matrix tests**

- Assert every PRD action by object, status, identity, and handler state.
- Include Transfer, management reassignment, Void/Close, verification transfer, confirmation transfer, Creator Edit, Reporter/Tester Return/Reopen/Activate.
- Verify denied identities do not see or execute actions.

**Step 2: Write failing reactivation and override tests**

- Canceled objects reactivate to Pending Assignment without owner and In Processing with restored/selected owner.
- Completed requirement supports manual Reactivate but active related Bug does not auto-reopen it.
- Automatic routing rejects selected target status.
- Override mode enforces configured override roles and records complete old/new audit data.

**Step 3: Implement default transitions and runtime non-transition commands**

- Add missing transitions and action metadata.
- Use action category/placement consistently.
- Keep comments/history as non-status actions but expose them consistently where required.

**Step 4: Implement reactivation and routing-mode enforcement**

- Resolve target status from restored/selected owner.
- Enforce routing mode before accepting selected target status.
- Capture old Bug type before domain mutation and persist full audit metadata.

**Step 5: Verify Task 6**

Run:

```powershell
pytest -q backend/tests/test_default_workflow_templates_api.py backend/tests/test_workflow_runtime_api.py backend/tests/test_bug_workflow_api.py
Set-Location frontend; npm test -- workflowRuntimeActions; npm run build
```

Expected: action matrices, reactivation, and override tests pass.

### Task 7: Creator Tracking, Watch Coverage, And Project Board (G10, G11)

**Files:**
- Modify: requirement/task/bug/test-run create services and controllers
- Modify: `backend/app/services/object_watch_service.py`
- Modify: `backend/app/services/dashboard_service.py`
- Modify: `backend/app/views/dashboard_view.py`
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: list views for requirement/task/bug/test run
- Modify: test-run detail view
- Test: `backend/tests/test_dashboard_workbench_api.py`
- Test: `backend/tests/test_object_watch_api.py`
- Test: `frontend/src/utils/workbenchViewModel.test.mjs`

**Step 1: Write failing creator/watch tests**

- Authenticated creates persist server-derived creator ID.
- New objects immediately appear in Created By Me without direct DB updates.
- Requirement/task/Bug/test-run detail and list contexts can watch/unwatch.
- Mention and manual sources deduplicate effective watch while preserving source history.

**Step 2: Write failing project-board tests**

- Include uniterated work items.
- Filter/group by project, iteration, status, owner, and handler.
- Preserve runtime actions and permission scope.

**Step 3: Implement creator and watch coverage**

- Pass actors into all create services.
- Add TestRun to object-watch model mapping.
- Add list-row toggle without duplicating detail state logic.

**Step 4: Implement board view model**

- Return normalized items plus grouping dimensions from backend.
- Add an uniterated bucket.
- Add explicit frontend controls for group mode and filters.

**Step 5: Verify Task 7**

Run:

```powershell
pytest -q backend/tests/test_dashboard_workbench_api.py backend/tests/test_object_watch_api.py backend/tests/test_notification_api.py
Set-Location frontend; npm test -- workbenchViewModel; npm run build
```

Expected: tracking and board tests pass.

### Task 8: Configurable Exception Center (G12)

**Files:**
- Create: `backend/app/models/exception_rule.py`
- Create: `backend/app/views/exception_rule_view.py`
- Create: `backend/app/services/exception_rule_service.py`
- Create: `backend/app/controllers/exception_rule_controller.py`
- Create: `backend/alembic/versions/20260710_002_exception_rules.py`
- Modify: `backend/app/services/exception_center_service.py`
- Modify: `backend/app/services/dashboard_service.py`
- Modify: `frontend/src/views/DashboardView.vue`
- Add admin configuration UI in the existing admin structure
- Test: `backend/tests/test_exception_center_api.py`
- Test: `frontend/src/utils/workbenchViewModel.test.mjs`

**Step 1: Write failing exception boundary tests**

- Cover all eight PRD exception types.
- Verify before/at/after threshold behavior.
- Calculate duration from the latest relevant state operation, not creation time.
- Completed requirement with active related Bug appears as exception without reopening.
- Verify role/project visibility boundaries.

**Step 2: Run tests and confirm failure**

Run: `pytest -q backend/tests/test_exception_center_api.py backend/tests/test_dashboard_workbench_api.py`

Expected: missing rules and state-age calculations fail.

**Step 3: Implement rule persistence and evaluation**

- Add system defaults with project/object/priority/status override resolution.
- Emit exception key, label, entered-at, threshold, and overdue duration.
- Keep exception queries read-only.

**Step 4: Implement filters and admin configuration**

- Add project, type, priority, status, handler, owner, and duration filters.
- Add restrained rule-management UI under admin.

**Step 5: Verify Slice C**

Run:

```powershell
pytest -q backend/tests/test_exception_center_api.py backend/tests/test_dashboard_workbench_api.py backend/tests/test_object_watch_api.py
Set-Location frontend; npm test; npm run build
```

Expected: workbench and exception-center suite passes.

### Task 9: Workflow Designer Runtime Configuration Closure (G13)

**Files:**
- Modify: `backend/app/services/workflow_definition_service.py`
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/views/workflow_definition_view.py`
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Modify: `frontend/src/components/WorkflowActionButtons.vue`
- Add focused frontend config serializers/tests
- Test: `backend/tests/test_workflow_definition_api.py`
- Test: `backend/tests/test_workflow_runtime_api.py`
- Test: frontend workflow designer utility tests

**Step 1: Write failing schema validation tests**

- Invalid routes, missing select options, unknown validators/triggers/post-actions, and illegal roles fail save.
- Valid condition/form/ui/validator/handler configurations round-trip without data loss.
- Unsupported runtime components return a configuration error rather than being ignored.

**Step 2: Run tests and confirm failure**

Run: `pytest -q backend/tests/test_workflow_definition_api.py backend/tests/test_workflow_runtime_api.py`

Expected: advanced config validation/execution tests fail.

**Step 3: Implement controlled schemas and runtime dispatch**

- Define whitelisted config shapes.
- Dispatch known validators, notifications, and post-actions.
- Reject unsupported types.

**Step 4: Extend designer panels**

- Add condition routing, form fields/options, validator, button placement, override roles, trigger, and post-action controls.
- Preserve unknown historical read-only data until migrated; do not silently drop it on save.

**Step 5: Verify Task 9**

Run:

```powershell
pytest -q backend/tests/test_workflow_definition_api.py backend/tests/test_workflow_runtime_api.py
Set-Location frontend; npm test -- workflow; npm run build
```

Expected: designer round-trip and runtime config tests pass.

### Task 10: Canonical Status Cleanup, Iteration Cancel, And Full Verification (G14)

**Files:**
- Create: canonical-status Alembic migration
- Modify: requirement/task models, views, services, filters, and labels
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/services/work_item_service.py`
- Modify: `backend/app/services/iteration_service.py`
- Modify: `frontend/src/views/RequirementsView.vue`
- Modify: `frontend/src/views/RequirementDetailView.vue`
- Modify: `frontend/src/views/TasksView.vue`
- Modify: `frontend/src/views/TaskDetailView.vue`
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/views/IterationDetailView.vue`
- Modify: shared status label utilities
- Test: all workflow/workbench tests

**Step 1: Write failing canonical-status tests**

- API create/read/filter returns only canonical requirement/task/Bug statuses.
- Legacy aliases are rejected after migration.
- Terminal and unassigned queries use canonical values.
- Iteration Cancel is exposed and uses the same gate as Complete.

**Step 2: Implement migration and remove compatibility mappings**

- Map existing old statuses to canonical values in a transaction-safe migration.
- Replace frontend labels, options, filters, and comparisons.
- Delete runtime alias candidates and stale terminal-status sets after tests use canonical fixtures.

**Step 3: Add iteration cancel UI**

- Load available iteration transitions or invoke the unified runtime action component.
- Show gate errors without changing iteration state.
- Keep the existing fixed desktop layout.

**Step 4: Prove legacy deletion safety**

Run repository searches for old statuses, old fixed transition endpoints, hard-coded Bug types, and duplicate assign/claim logic. Allow matches only in migrations, historical docs, and explicit migration tests.

**Step 5: Run full backend verification**

Run: `pytest -q backend/tests`

Expected: all backend tests pass with zero failures.

**Step 6: Run full frontend verification**

Run:

```powershell
Set-Location frontend
npm test
npm run build
```

Expected: all frontend tests pass and Vite production build succeeds.

**Step 7: Fixed desktop UI verification**

- Start backend and frontend dev servers on available ports.
- Verify task creation/completion, Bug classification/verification, requirement terminal gates, workbench tracking/board/exceptions, and iteration cancel at the project fixed desktop viewport.
- Do not move the viewport or add mobile acceptance checks.

**Step 8: Final cleanup report**

- List modified and deleted files.
- List removed compatibility/duplicate implementations.
- Report exact tests/builds run.
- Report migration and residual risks.
