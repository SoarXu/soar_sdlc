# Current Handler Workbench Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make work item owners behave as current handlers and make the workbench show the current user's actionable queue.

**Architecture:** Keep existing `owner_id` columns for requirements, tasks, and bugs, but treat them as current handler fields. Add workflow/transition assignment helpers, explicit assign endpoints, status-operation history, and workbench filtering by current handler. Defer a deeper test-case execution handler model and keep `default_tester_id` as the test-case handler for now.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, Vue 3, Element Plus, Vite.

---

### Task 1: Add Assignment Request Schema

**Files:**
- Modify: `backend/app/views/status_operation_view.py`
- Test: none directly; used by API tests in later tasks.

**Step 1: Add schema**

Add:

```python
class AssignOwnerRequest(BaseModel):
    owner_id: int
    remark: str | None = None
```

**Step 2: Verify import**

Run:

```bash
E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_model_metadata.py -q
```

Expected: existing metadata tests pass.

### Task 2: Add Shared Assignment Service

**Files:**
- Create: `backend/app/services/assignment_service.py`
- Test: `backend/tests/test_assignment_api.py`

**Step 1: Write failing tests**

Create tests that:

- Create a requirement with `owner_id = user_a`.
- POST assign to `user_b`.
- Assert `owner_id == user_b`.
- Assert status operation history includes action `assign`.
- Assert assigning a closed requirement returns `400`.

Use existing project/user helpers from nearby API tests where possible.

Run:

```bash
E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_assignment_api.py -q
```

Expected: fail because endpoints/service do not exist.

**Step 2: Implement service**

Create helper functions:

```python
def assign_requirement_owner(db: Session, requirement_id: int, payload: AssignOwnerRequest, actor_id: int | None = None) -> Requirement: ...
def assign_task_owner(db: Session, task_id: int, payload: AssignOwnerRequest, actor_id: int | None = None) -> Task: ...
def assign_bug_owner(db: Session, bug_id: int, payload: AssignOwnerRequest, actor_id: int | None = None) -> Bug: ...
```

Use a private helper to:

- Load non-deleted object.
- Reject terminal statuses.
- Store previous owner.
- Update `owner_id`.
- Insert `StatusOperationLog(action="assign", from_status=current_status, to_status=current_status, remark=...)`.
- Commit and refresh.

Terminal statuses:

- Requirement: `done`, `closed`
- Task: `done`, `closed`
- Bug: `closed`

**Step 3: Run tests**

Run:

```bash
E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_assignment_api.py -q
```

Expected: assignment service tests pass after endpoints are added in Task 3.

### Task 3: Add Assign Endpoints

**Files:**
- Modify: `backend/app/controllers/requirement_controller.py`
- Modify: `backend/app/controllers/task_controller.py`
- Modify: `backend/app/controllers/bug_controller.py`
- Test: `backend/tests/test_assignment_api.py`

**Step 1: Add route functions**

Add:

```python
@router.post("/{requirement_id}/assign", response_model=RequirementRead)
def assign_requirement(...):
    return assign_requirement_owner(db, requirement_id, payload, actor_id=current_user.id if available else None)
```

Repeat for tasks and bugs.

If existing controllers do not consistently inject current user, pass `None` first and leave actor wiring for a later auth-hardening task.

**Step 2: Run tests**

Run:

```bash
E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_assignment_api.py -q
```

Expected: pass.

### Task 4: Add Transition Handler Calculation

**Files:**
- Modify: `backend/app/services/requirement_service.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/services/bug_service.py`
- Test: `backend/tests/test_current_handler_workflow_api.py`

**Step 1: Write failing tests**

Add tests for:

- Requirement submit validation assigns tester/test lead.
- Requirement validation failed assigns developer.
- Bug resolve assigns tester/test lead.
- Bug verify failed assigns developer.
- Bug activate from closed assigns developer and still requires confirm step.

Run:

```bash
E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_current_handler_workflow_api.py -q
```

Expected: fail because transitions do not update handlers consistently.

**Step 2: Implement minimal helpers**

In each service, after status validation and before transition commit, set `owner_id` using existing project-team defaults:

- Requirement to validation: `default_tester_id(db, project_id)`.
- Requirement validation failed / active: `default_developer_id(db, project_id)`.
- Bug resolve: `default_tester_id(db, project_id)`.
- Bug verify failed / activate: `default_bug_owner_id(db, project_id)`.
- Task active/doing: `default_developer_id(db, project_id)`.

Do not introduce a new rule engine yet; use current project-team helper functions.

**Step 3: Run tests**

Run:

```bash
E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_current_handler_workflow_api.py backend\tests\test_bug_workflow_api.py backend\tests\test_requirement_task_api.py -q
```

Expected: pass.

### Task 5: Change Workbench Filtering to Current Handler

**Files:**
- Modify: `backend/app/services/dashboard_service.py`
- Test: `backend/tests/test_dashboard_workbench_api.py`

**Step 1: Write failing tests**

Add tests that:

- Create two users.
- Create work items in the same project/iteration assigned to different users.
- Call workbench as user A.
- Assert only user A's non-terminal assigned items appear in default workbench.
- Assert a lead/team view can still see scoped project items.

Run:

```bash
E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_dashboard_workbench_api.py -q
```

Expected: fail because current logic includes scoped project items.

**Step 2: Implement filtering**

Change `_filter_items_for_role` so default non-admin user behavior is:

```python
if view_mode == "all":
    return items
if view_mode == "lead" and scoped_project_ids:
    return project scoped items
if user_id:
    return [item for item in items if item.owner_id == user_id and not terminal]
```

Keep test cases mapped through `owner_id=item.default_tester_id`.

Add terminal check helper for requirement/task/bug.

**Step 3: Run tests**

Run:

```bash
E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_dashboard_workbench_api.py -q
```

Expected: pass.

### Task 6: Add Frontend Assign API and UI

**Files:**
- Modify: `frontend/src/api/requirements.js`
- Modify: `frontend/src/api/tasks.js`
- Modify: `frontend/src/api/bugs.js`
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: list/detail pages as needed for visible labels.
- Test: `npm run build`

**Step 1: Add API functions**

Add:

```javascript
export function assignRequirement(id, payload) {
  return http.post(`/requirements/${id}/assign`, payload)
}
```

Repeat for tasks and bugs.

**Step 2: Add workbench assign action**

In `DashboardView.vue`, add "指派" for non-terminal requirement/task/bug items.

Dialog fields:

- Handler select from `owners` or all users already loaded on the page.
- Remark textarea.

Submit calls the appropriate assign API, closes dialog, reloads workbench.

**Step 3: Rename labels**

Change active-work labels from "负责人" to "当前处理人" in workbench and relevant list pages.

**Step 4: Build**

Run:

```bash
npm run build
```

Expected: Vite build exits `0`; existing Rollup warnings may remain.

### Task 7: Full Regression

**Files:**
- No source changes unless tests expose issues.

**Step 1: Run backend focused tests**

Run:

```bash
E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend\tests\test_assignment_api.py backend\tests\test_current_handler_workflow_api.py backend\tests\test_dashboard_workbench_api.py backend\tests\test_bug_workflow_api.py backend\tests\test_requirement_task_api.py -q
```

Expected: pass.

**Step 2: Run frontend build**

Run:

```bash
npm run build
```

Expected: pass.

**Step 3: Manual smoke check**

Start backend/frontend if needed and verify:

- A requirement assigned to user A appears only for user A.
- Manual assign moves it to user B's workbench.
- Bug resolve moves the bug to the tester/verifier.
- Closed/done items are hidden from default my workbench.
