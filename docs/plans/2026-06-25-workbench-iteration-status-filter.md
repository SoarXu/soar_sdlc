# Workbench Iteration Status Filter Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the workbench return all in-scope iterations while keeping "only active iterations" as a default-on frontend filter.

**Architecture:** Backend workbench scope should be determined by project participation and the mine/all view, not by iteration status. Frontend adds a default-on active-iteration checkbox next to the existing empty-iteration filter, and all list/board/stats views reuse the existing `filteredIterations` computed chain.

**Tech Stack:** FastAPI, SQLAlchemy, Pytest, Vue 3, Element Plus.

---

### Task 1: Backend Workbench Scope Tests

**Files:**
- Modify: `backend/tests/test_dashboard_workbench_api.py`

**Step 1: Replace the active-only test**

Change `test_workbench_only_shows_active_iterations_for_all_views` so it verifies both planning and active iterations are returned by `/api/v1/dashboard/workbench`.

**Step 2: Add a mine-scope non-active iteration test**

Add a test where a developer is a `ProjectMember` with `is_workbench_participant=True`, the project has a planning iteration, and `/api/v1/dashboard/workbench?user_id=<developer>` includes that planning iteration.

**Step 3: Run target tests to verify failure**

Run:

```bash
E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests/test_dashboard_workbench_api.py::test_workbench_returns_all_iteration_statuses backend/tests/test_dashboard_workbench_api.py::test_developer_workbench_scope_includes_non_active_project_iterations -q
```

Expected: fail because backend filters `Iteration.status == "active"`.

### Task 2: Backend Workbench Query

**Files:**
- Modify: `backend/app/services/dashboard_service.py`
- Test: `backend/tests/test_dashboard_workbench_api.py`

**Step 1: Remove status filter**

In `get_workbench`, change the iteration query from:

```python
.filter(Iteration.deleted == 0, Iteration.status == "active")
```

to:

```python
.filter(Iteration.deleted == 0)
```

**Step 2: Run backend target tests**

Run:

```bash
E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests/test_dashboard_workbench_api.py -q
```

Expected: pass.

### Task 3: Frontend Active Iteration Filter

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`

**Step 1: Add filter state**

Add:

```js
const onlyActiveIterations = ref(true)
```

near `hideEmptyIterations`.

**Step 2: Add checkbox UI**

Add an Element Plus checkbox near "仅显示有工作项":

```vue
<el-checkbox v-model="onlyActiveIterations" class="workbench-checkbox">仅显示进行中</el-checkbox>
```

**Step 3: Apply filter**

In `filteredIterations`, add:

```js
.filter((iteration) => !onlyActiveIterations.value || iteration.status === 'active')
```

before the empty-iteration filter.

**Step 4: Update page copy**

Change the workbench description from active-only wording to project-member scope plus filter wording.

### Task 4: Verification

**Files:**
- `backend/tests/test_dashboard_workbench_api.py`
- `frontend/src/views/DashboardView.vue`

**Step 1: Run backend tests**

Run:

```bash
E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests/test_dashboard_workbench_api.py -q
```

Expected: pass.

**Step 2: Run frontend build**

Run:

```bash
npm --prefix frontend run build
```

Expected: pass.

