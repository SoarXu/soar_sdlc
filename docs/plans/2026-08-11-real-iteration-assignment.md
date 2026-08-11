# 真实迭代分配 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove default requirement-pool iterations and require every requirement to use a project-scoped, non-terminal real iteration.

**Architecture:** Centralize eligible-iteration selection and validation in the backend, with automatic creation of an unstarted iteration only when a project has no usable target. Migrate legacy pool contents before removing the pool schema, then use the same eligible-iteration predicate in the frontend forms and the project-detail work-pool summary.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, Vue 3, Element Plus, Node built-in assertions, Vite.

---

### Task 1: Capture backend acceptance rules with failing API tests

**Files:**
- Create: `backend/tests/test_requirement_real_iteration_assignment_api.py`
- Modify: `backend/tests/test_requirement_task_api.py`

**Step 1: Write failing create and update tests**

Add tests proving that a requirement POST without `iteration_id` returns a validation error, a closed iteration is rejected, a project-out-of-scope iteration is rejected, and a project-scoped unstarted or in-progress iteration is accepted. Add update coverage that rejects clearing or changing a requirement to a closed iteration.

**Step 2: Write the automatic-target tests**

Exercise the shared target resolver through an unlinked task and Bug creation for a project without a usable iteration. Assert that one real unstarted iteration is created, its `is_requirement_pool` flag is false, and both work items use its ID.

**Step 3: Run the focused tests and observe failure**

Run: `pytest tests/test_requirement_real_iteration_assignment_api.py tests/test_requirement_task_api.py -q`

Expected: FAIL because current code resolves missing values to the requirement pool and accepts the pool as a requirement target.

### Task 2: Replace requirement-pool resolution with eligible real-iteration resolution

**Files:**
- Modify: `backend/app/services/requirement_pool_service.py`
- Modify: `backend/app/services/requirement_service.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/services/bug_service.py`
- Modify: `backend/app/services/iteration_service.py`
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/services/requirement_import_service.py`

**Step 1: Implement the shared resolver**

Replace pool-specific helpers with a service that identifies project-scoped iterations whose workflow state category is `start` or `in_progress`, rejects null requirement targets, rejects terminal and out-of-scope targets, and selects an existing eligible iteration for non-requirement fallbacks. When no eligible target exists for a task or Bug fallback, create one unstarted real iteration with the default system iteration workflow and project membership.

**Step 2: Apply the resolver at every mutation boundary**

Require `iteration_id` on requirement creation and validate it on requirements updates, import creation, project changes, API linking and workflow-driven moves. Replace all task/Bug pool fallbacks with the eligible real-iteration resolver. Change iteration unlink or scope-removal paths so they move items to a real eligible target rather than a pool; never assign `None` to a requirement.

**Step 3: Run focused backend tests**

Run: `pytest tests/test_requirement_real_iteration_assignment_api.py tests/test_requirement_task_api.py tests/test_iteration_detail_api.py tests/test_workflow_runtime_api.py -q`

Expected: PASS, including existing iteration-history coverage updated for real targets.

### Task 3: Migrate and remove legacy requirement-pool persistence

**Files:**
- Create: `backend/alembic/versions/20260811_001_remove_requirement_pool_iterations.py`
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/models/iteration.py`
- Modify: `backend/app/services/project_service.py`
- Modify: `backend/app/db/schema.py`
- Modify: `backend/tests/conftest.py`
- Modify: `backend/tests/test_requirement_pool_repository_contract.py`

**Step 1: Write the migration contract test**

Add a migration-oriented test or repository contract asserting that project creation no longer creates a pool, project detail has no `requirement_pool_iteration_id`, and real iteration assignment is present for every migrated requirement.

**Step 2: Implement the migration**

For each active project with a pool, lock its records, choose an in-progress iteration or an unstarted iteration, or create an unstarted real iteration when neither exists. Move pool requirements, tasks and Bugs to that target while retaining their history, delete the pool and its project membership, then drop `projects.requirement_pool_iteration_id` and `iterations.is_requirement_pool`. Update bootstrap schema, ORM models, project serialization and test cleanup to match.

**Step 3: Run migration and project tests**

Run: `pytest tests/test_requirement_pool_repository_contract.py tests/test_program_project_api.py tests/test_project_permission_boundary_api.py -q`

Expected: PASS with no code path or fixture requiring a default pool.

### Task 4: Require eligible iterations in requirement forms and aggregate the project work pool

**Files:**
- Create: `frontend/src/views/requirementRealIterationAssignment.test.mjs`
- Modify: `frontend/src/views/RequirementsView.vue`
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/utils/requirementPoolIterations.js`

**Step 1: Write a failing frontend source contract**

Assert that both requirement forms mark the iteration selector as required, do not set an implicit pool ID, do not include terminal iterations, and reject submission without a selected iteration. Assert that project-detail work-pool filters use the union of in-progress and unstarted iteration IDs for requirements, tasks and Bugs, rather than a `requirement_pool` row.

**Step 2: Implement the minimum interface changes**

Replace the pool utility with an eligible-iteration utility. Use it in the requirement list and project detail forms; clear any stale terminal selection and show a required-field validation message on submit. Remove pool-only filter, selection and “纳入正式迭代” actions. Retain the work-pool band and populate its three counters and filtered lists from all project work items in eligible iterations.

**Step 3: Run the frontend contract test**

Run: `npm test requirementRealIterationAssignment`

Expected: PASS and output confirms the real-iteration selection and aggregation contract.

### Task 5: Verify the complete change

**Files:**
- Test: `backend/tests/test_requirement_real_iteration_assignment_api.py`
- Test: `frontend/src/views/requirementRealIterationAssignment.test.mjs`

**Step 1: Run all backend tests**

Run: `pytest -q`

Expected: PASS.

**Step 2: Run all frontend tests and production build**

Run: `npm test && npm run build`

Expected: all source tests pass and Vite completes the production build without errors.

**Step 3: Perform a focused manual workflow check**

Create a project without iterations and confirm requirement creation requires a real iteration after the UI supplies or the project has an unstarted one. Confirm closed iterations are unavailable. Create an in-progress and an unstarted iteration, then confirm the project-detail work-pool counters and lists include both iterations' requirements, tasks and Bugs.

**Step 4: Git handling**

Do not stage, commit, push, create a pull request, or merge. Request the required delivery instruction after implementation and verification.
