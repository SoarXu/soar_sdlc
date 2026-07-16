# Workbench Workflow Default Template Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the PRD-defined default workflow templates, cross-object blocking rules, workbench restructuring, and watch/mention support across backend and frontend.

**Architecture:** Keep the existing FastAPI + Vue workflow stack, but move object behavior behind one default-template model: workflow definitions provide the states/transitions/actions, workflow runtime enforces handlers and blockers, and the dashboard/workbench renders queues and actions from runtime output instead of hard-coded object rules. Proceed in the main workspace because no dedicated worktree was requested.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, pytest, Vue 3, Vite, Element Plus

---

### Task 1: Lock The PRD Rules With New Backend Tests

**Files:**
- Create: `backend/tests/test_default_workflow_templates_api.py`
- Modify: `backend/tests/test_workflow_runtime_api.py`
- Modify: `backend/tests/test_dashboard_workbench_api.py`
- Reference: `docs/prd/2026-07-08-workbench-workflow-layering-prd.md`

**Step 1: Write failing workflow-template tests**

Add tests for:
- Bug default statuses and close blocking by directly related tasks
- Task branch defaults and branch-specific confirmation paths
- Requirement completion/cancel blocking by directly related tasks/Bugs
- Iteration completion/cancel blocking by directly included objects
- Project close blocking by directly scoped objects

**Step 2: Write failing workbench-shape tests**

Add tests for:
- `待处理 / 未分派 / 我发起/关注 / 异常中心 / 项目看板` response grouping
- current-handler-based queue placement
- unassigned queue placement
- exception-center response content

**Step 3: Run targeted backend tests and verify failures**

Run:
```powershell
pytest backend\tests\test_default_workflow_templates_api.py backend\tests\test_workflow_runtime_api.py backend\tests\test_dashboard_workbench_api.py -q
```

Expected:
- new tests fail because runtime, workbench, and blocking logic are not implemented yet

**Step 4: Commit the red tests**

```powershell
git add backend\tests\test_default_workflow_templates_api.py backend\tests\test_workflow_runtime_api.py backend\tests\test_dashboard_workbench_api.py
git commit -m "test: lock default workflow template behavior"
```

### Task 2: Add Schema Support For Default Templates, Watches, Mentions, And Exceptions

**Files:**
- Create: `backend/alembic/versions/20260709_001_workbench_workflow_default_templates.py`
- Create: `backend/app/models/object_watch.py`
- Create: `backend/app/models/work_item_comment.py`
- Modify: `backend/app/models/workflow_definition.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/models/notification.py`

**Step 1: Add failing migration smoke coverage if needed**

If the repo already validates migrations indirectly, add assertions there; otherwise rely on upgrade test commands later.

**Step 2: Write the Alembic migration**

Include:
- default-template workflow seed tables/rows as needed by current schema
- `object_watch`
- `work_item_comments`
- any indexes needed for queue and mention lookups

**Step 3: Add SQLAlchemy models**

Model the new tables with explicit fields for:
- watcher/source/enabled
- comment object type/object id/author/body/mentions metadata

**Step 4: Run migration-oriented tests or a local upgrade**

Run:
```powershell
pytest backend\tests\test_db_session.py -q
```

Expected:
- schema/model loading stays green

**Step 5: Commit schema work**

```powershell
git add backend\alembic\versions\20260709_001_workbench_workflow_default_templates.py backend\app\models\object_watch.py backend\app\models\work_item_comment.py backend\app\models\workflow_definition.py backend\app\models\notification.py backend\app\models\__init__.py
git commit -m "feat: add workflow template and watch schema support"
```

### Task 3: Seed And Serve The Default Workflow Templates

**Files:**
- Create: `backend/app/services/default_workflow_template_service.py`
- Modify: `backend/app/services/workflow_definition_service.py`
- Modify: `backend/app/services/workflow_service.py`
- Modify: `backend/app/services/workflow_catalog.py`
- Modify: `backend/app/views/workflow_definition_view.py`
- Modify: `backend/tests/test_workflow_definition_api.py`

**Step 1: Write failing template-definition tests**

Cover:
- requirement/task/Bug/iteration/project default definitions exist
- states and transitions match the PRD baseline
- template metadata flags the baseline as the default template

**Step 2: Implement the template seeding/serving service**

Add one place that creates/updates:
- default states
- transitions
- form config
- handler-routing config
- validator config
- UI config/list display priorities

**Step 3: Expose template metadata through existing definition APIs**

Return enough fields for frontend configuration screens to distinguish:
- baseline default template
- later editable project-level overrides

**Step 4: Run targeted definition tests**

Run:
```powershell
pytest backend\tests\test_workflow_definition_api.py -q
```

Expected:
- tests pass with seeded default definitions

**Step 5: Commit template definition work**

```powershell
git add backend\app\services\default_workflow_template_service.py backend\app\services\workflow_definition_service.py backend\app\services\workflow_service.py backend\app\services\workflow_catalog.py backend\app\views\workflow_definition_view.py backend\tests\test_workflow_definition_api.py
git commit -m "feat: seed default workflow templates"
```

### Task 4: Extend Workflow Runtime For Conditional Routing, Handler Rules, And Blocking Validators

**Files:**
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/services/workflow_engine.py`
- Modify: `backend/app/views/workflow_runtime_view.py`
- Modify: `backend/app/services/status_operation_service.py`
- Modify: `backend/tests/test_workflow_runtime_api.py`
- Modify: `backend/tests/test_status_operation_service.py`

**Step 1: Write failing runtime tests for the new execution model**

Cover:
- Bug type -> target status routing
- manual target-status selection / override constraints
- current-handler changes on assignment, submit confirmation, verification, reactivate
- blocking validators for requirement/Bug/iteration/project terminal actions

**Step 2: Extend the runtime request/response schema**

Add fields for:
- selected form values
- resolved target status
- manual override reason if applicable
- clearer validation failure payloads

**Step 3: Implement validator and routing evaluation**

Add runtime helpers for:
- action-form condition matching
- linked-object blocker queries
- handler-source resolution
- terminal-state compatibility checks

**Step 4: Record richer status-operation history**

Persist:
- selected Bug type
- resolved target status
- manual override details
- handler transitions
- blocker failure messages where relevant

**Step 5: Run targeted runtime tests**

Run:
```powershell
pytest backend\tests\test_workflow_runtime_api.py backend\tests\test_status_operation_service.py -q
```

Expected:
- runtime tests pass with conditional routing and blocker enforcement

**Step 6: Commit runtime work**

```powershell
git add backend\app\services\workflow_runtime_service.py backend\app\services\workflow_engine.py backend\app\views\workflow_runtime_view.py backend\app\services\status_operation_service.py backend\tests\test_workflow_runtime_api.py backend\tests\test_status_operation_service.py
git commit -m "feat: add workflow runtime routing and blockers"
```

### Task 5: Reconcile Object Services And Controllers With The Default Template Model

**Files:**
- Modify: `backend/app/services/requirement_service.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/services/bug_service.py`
- Modify: `backend/app/services/iteration_service.py`
- Modify: `backend/app/services/project_service.py`
- Modify: `backend/app/controllers/requirement_controller.py`
- Modify: `backend/app/controllers/task_controller.py`
- Modify: `backend/app/controllers/bug_controller.py`
- Modify: `backend/app/controllers/iteration_controller.py`
- Modify: `backend/app/controllers/project_controller.py`
- Modify: `backend/tests/test_bug_workflow_api.py`
- Modify: `backend/tests/test_requirement_task_api.py`
- Modify: `backend/tests/test_iteration_detail_api.py`

**Step 1: Write failing compatibility tests**

Cover:
- old object endpoints still work or fail with explicit deprecation/constraint behavior
- direct object services no longer bypass the new blocker rules
- linked-task creation inherits source current handler by default

**Step 2: Refactor object-level status actions**

Choose one consistent path:
- either wrap old endpoints around workflow runtime actions
- or hard-fail deprecated paths and migrate the frontend to runtime actions

Document the chosen compatibility behavior in code comments where needed.

**Step 3: Move legacy implicit object coupling behind configured validators**

Remove object-specific hidden transitions that conflict with the PRD baseline:
- requirement auto-complete from task changes
- Bug auto-close side effects
- task-driven upper-level transitions

**Step 4: Run targeted domain tests**

Run:
```powershell
pytest backend\tests\test_bug_workflow_api.py backend\tests\test_requirement_task_api.py backend\tests\test_iteration_detail_api.py -q
```

Expected:
- tests pass under the new default-template behavior

**Step 5: Commit service/controller reconciliation**

```powershell
git add backend\app\services\requirement_service.py backend\app\services\task_service.py backend\app\services\bug_service.py backend\app\services\iteration_service.py backend\app\services\project_service.py backend\app\controllers\requirement_controller.py backend\app\controllers\task_controller.py backend\app\controllers\bug_controller.py backend\app\controllers\iteration_controller.py backend\app\controllers\project_controller.py backend\tests\test_bug_workflow_api.py backend\tests\test_requirement_task_api.py backend\tests\test_iteration_detail_api.py
git commit -m "refactor: route object lifecycle through workflow templates"
```

### Task 6: Rebuild Workbench Backend For New Queues And Exception Center

**Files:**
- Modify: `backend/app/services/dashboard_service.py`
- Modify: `backend/app/controllers/dashboard_controller.py`
- Modify: `backend/app/views/dashboard_view.py`
- Create: `backend/app/services/exception_center_service.py`
- Modify: `backend/app/services/project_team_service.py`
- Modify: `backend/tests/test_dashboard_workbench_api.py`
- Modify: `backend/tests/test_unassigned_work_items_api.py`

**Step 1: Write failing queue and exception tests**

Cover:
- current-handler queue (`待处理`)
- unassigned queue (`未分派`)
- created/watched/mentioned grouping
- exception-center lists
- role-specific visibility

**Step 2: Expand the dashboard response model**

Return separate sections for:
- pending handling
- unassigned
- created by me
- watched by me
- mentioned me
- project board
- exception center

**Step 3: Implement exception-center queries**

Use explicit query helpers for:
- timeout conditions
- verified-not-closed
- repeated activation
- high-priority unprocessed

**Step 4: Keep old board/list data until frontend migration is complete**

If needed, serve both:
- new normalized queue sections
- legacy iteration board data

so the frontend can migrate incrementally without breaking.

**Step 5: Run targeted workbench tests**

Run:
```powershell
pytest backend\tests\test_dashboard_workbench_api.py backend\tests\test_unassigned_work_items_api.py -q
```

Expected:
- new queue and exception tests pass

**Step 6: Commit workbench backend changes**

```powershell
git add backend\app\services\dashboard_service.py backend\app\controllers\dashboard_controller.py backend\app\views\dashboard_view.py backend\app\services\exception_center_service.py backend\app\services\project_team_service.py backend\tests\test_dashboard_workbench_api.py backend\tests\test_unassigned_work_items_api.py
git commit -m "feat: add default workbench queues and exception center"
```

### Task 7: Implement Watches, Comments, Mentions, And Notifications

**Files:**
- Create: `backend/app/views/work_item_comment_view.py`
- Create: `backend/app/services/work_item_comment_service.py`
- Create: `backend/app/controllers/work_item_comment_controller.py`
- Create: `backend/app/views/object_watch_view.py`
- Create: `backend/app/services/object_watch_service.py`
- Create: `backend/app/controllers/object_watch_controller.py`
- Modify: `backend/app/controllers/router.py`
- Modify: `backend/app/services/notification_service.py`
- Modify: `backend/tests/test_notification_api.py`
- Create: `backend/tests/test_work_item_comment_api.py`
- Create: `backend/tests/test_object_watch_api.py`

**Step 1: Write failing comment/watch tests**

Cover:
- manual watch/unwatch
- comment creation on requirement/task/Bug
- `@` mention parsing from selected user IDs
- notification creation
- mention adds watch relation

**Step 2: Implement backend watch APIs**

Support:
- watch
- unwatch
- list watchers if needed by UI

**Step 3: Implement comment and mention APIs**

Persist:
- comment body
- mentioned user IDs
- object type/id
- author

Then create notifications and mention-sourced watch relations.

**Step 4: Run targeted collaboration tests**

Run:
```powershell
pytest backend\tests\test_work_item_comment_api.py backend\tests\test_object_watch_api.py backend\tests\test_notification_api.py -q
```

Expected:
- comment, mention, and watch behavior passes

**Step 5: Commit collaboration features**

```powershell
git add backend\app\views\work_item_comment_view.py backend\app\services\work_item_comment_service.py backend\app\controllers\work_item_comment_controller.py backend\app\views\object_watch_view.py backend\app\services\object_watch_service.py backend\app\controllers\object_watch_controller.py backend\app\controllers\router.py backend\app\services\notification_service.py backend\tests\test_work_item_comment_api.py backend\tests\test_object_watch_api.py backend\tests\test_notification_api.py
git commit -m "feat: add work item watch and mention support"
```

### Task 8: Update Frontend Runtime Actions, Detail Views, And Collaboration UI

**Files:**
- Modify: `frontend/src/utils/workflowRuntimeActions.js`
- Modify: `frontend/src/utils/workflowRuntimeActions.test.mjs`
- Modify: `frontend/src/views/RequirementDetailView.vue`
- Modify: `frontend/src/views/TaskDetailView.vue`
- Modify: `frontend/src/views/BugDetailView.vue`
- Create: `frontend/src/components/WorkItemCommentPanel.vue`
- Create: `frontend/src/components/WatchToggleButton.vue`
- Create: `frontend/src/api/workItemComments.js`
- Create: `frontend/src/api/objectWatches.js`

**Step 1: Write failing frontend utility/component tests**

Cover:
- action splitting for primary/more buttons under new runtime metadata
- detail-page action rendering
- mention selection behavior in comment input

**Step 2: Update runtime-action helpers**

Handle:
- manual-target-status actions
- confirm-required actions
- detail/list visibility rules

**Step 3: Add reusable comment/watch UI**

Implement:
- watch toggle
- comment list + composer
- `@` user selector backed by known users

**Step 4: Integrate detail views**

Each of requirement/task/Bug detail pages should:
- render runtime actions
- surface blocker errors cleanly
- embed watch/comments

**Step 5: Run targeted frontend tests**

Run:
```powershell
npm run test -- workflowRuntimeActions
```

Expected:
- runtime helper tests pass

**Step 6: Commit detail/collaboration UI**

```powershell
git add frontend\src\utils\workflowRuntimeActions.js frontend\src\utils\workflowRuntimeActions.test.mjs frontend\src\views\RequirementDetailView.vue frontend\src\views\TaskDetailView.vue frontend\src\views\BugDetailView.vue frontend\src\components\WorkItemCommentPanel.vue frontend\src\components\WatchToggleButton.vue frontend\src\api\workItemComments.js frontend\src\api\objectWatches.js
git commit -m "feat: add runtime actions and collaboration UI"
```

### Task 9: Rebuild The Dashboard Workbench Frontend

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/api/dashboard.js`
- Modify: `frontend/src/styles.css`
- Create: `frontend/src/utils/workbenchViewModel.js`
- Create: `frontend/src/utils/workbenchViewModel.test.mjs`

**Step 1: Write failing dashboard-view-model tests**

Cover:
- queue grouping
- created/watched/mentioned tabs
- exception-center row mapping
- primary/secondary action placement

**Step 2: Introduce a dashboard view-model helper**

Map the backend response into:
- pending handling
- unassigned
- created/watched tabs
- exception center
- project board

**Step 3: Replace the old view switch in `DashboardView.vue`**

Update the page to match the PRD baseline:
- `待处理`
- `未分派`
- `异常中心`
- `我发起/关注`
- `项目看板`

**Step 4: Keep drag/move behavior only where still valid**

If project-board drag remains in scope, keep it under the board view only; do not let queue views depend on legacy board-only assumptions.

**Step 5: Run frontend build**

Run:
```powershell
npm run build
```

Expected:
- frontend build passes with the new workbench structure

**Step 6: Commit the dashboard rewrite**

```powershell
git add frontend\src\views\DashboardView.vue frontend\src\api\dashboard.js frontend\src\styles.css frontend\src\utils\workbenchViewModel.js frontend\src\utils\workbenchViewModel.test.mjs
git commit -m "feat: rebuild workbench around default workflow queues"
```

### Task 10: Full Verification And Cleanup

**Files:**
- Modify: `docs/prd/2026-07-08-workbench-workflow-layering-prd.md` (only if implementation notes or status references need narrow updates)
- Reference: all files changed above

**Step 1: Run the backend regression set**

Run:
```powershell
pytest backend\tests\test_default_workflow_templates_api.py backend\tests\test_workflow_runtime_api.py backend\tests\test_dashboard_workbench_api.py backend\tests\test_unassigned_work_items_api.py backend\tests\test_bug_workflow_api.py backend\tests\test_requirement_task_api.py backend\tests\test_iteration_detail_api.py backend\tests\test_work_item_comment_api.py backend\tests\test_object_watch_api.py backend\tests\test_notification_api.py -q
```

Expected:
- all selected backend tests pass

**Step 2: Run frontend verification**

Run:
```powershell
npm run build
```

Expected:
- production build succeeds

**Step 3: Run targeted manual workflow checks**

Verify manually in the app:
- requirement complete blocked by related task/Bug
- Bug close blocked by related task
- task submit-confirmation routes to confirmation handler
- workbench queues place items by current handler and assignment
- mentions add users to `我关注的/提到我的`

**Step 4: Commit final integration adjustments**

```powershell
git add .
git commit -m "feat: implement default workbench workflow templates"
```
