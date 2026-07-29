# Project Iteration Pool Display Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Show each project's requirement pool at the top of its iteration list and let users rename it through the existing iteration edit dialog.

**Architecture:** Keep the global iteration API delivery-only by default. Change only the project iteration page API to return its canonical requirement pool alongside delivery rows, then split and pin the pool in `ProjectDetailView`. Reuse the existing edit dialog with a pool-specific name-only mode; the backend pool guard remains authoritative.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3, Element Plus, Node source-contract tests.

---

### Task 1: Return The Pool From Project Iteration Pages

**Files:**
- Modify: `backend/app/services/project_service.py`
- Modify: `backend/tests/test_requirement_pool_iteration_api.py`
- Modify: `backend/tests/test_program_project_api.py`

**Step 1: Write the failing API tests**

Create a project, then assert its project iteration page contains exactly one pool with `is_requirement_pool is True`. Create delivery iterations and assert they remain present and normally ordered after the pool. Assert global `/iterations?project_id=...` still excludes the pool unless `include_requirement_pool=true` is supplied.

**Step 2: Run the focused tests to verify they fail**

Run:

```powershell
cd backend
pytest tests/test_requirement_pool_iteration_api.py tests/test_program_project_api.py -q
```

Expected: project iteration page does not contain the pool.

**Step 3: Implement the minimal query change**

In `list_project_iterations_page`, remove only the predicate that filters `Iteration.is_requirement_pool.is_(False)`. Preserve global `list_iterations(... include_requirement_pool=False)` behavior and all delivery-range filters outside this project-list query.

**Step 4: Run focused tests**

Run the same pytest command. Expected: PASS.

**Step 5: Commit**

```powershell
git add backend/app/services/project_service.py backend/tests/test_requirement_pool_iteration_api.py backend/tests/test_program_project_api.py
git commit -m "feat: show requirement pools in project iterations"
```

### Task 2: Pin The Pool And Reuse The Edit Dialog

**Files:**
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/views/requirementPoolProjectView.test.mjs`

**Step 1: Write failing frontend source-contract tests**

Assert that the project iteration view:

- derives one `projectRequirementPoolRow` from `projectIterationRows`;
- renders that row before `projectIterations`;
- no longer renders the separate requirements-toolbar rename button/dialog;
- opens the existing iteration dialog for the pool row;
- marks all fields except `name` disabled for a pool row;
- submits exactly `{ name }` when editing a pool;
- leaves ordinary iteration payloads and controls unchanged.

**Step 2: Run the test to verify it fails**

Run:

```powershell
cd frontend
npm test -- requirementPoolProjectView
```

Expected: FAIL because the pool is filtered out and rename uses a separate dialog.

**Step 3: Implement the display and edit mode**

Use `requirementPoolForProject(project.value, projectIterationRows.value)` or an equivalent canonical-reference lookup. Render a compact first row or a row before the paginated delivery table with the same columns. Mark its name with `requirementIterationLabel(pool)`.

Keep `projectIterations` as delivery-only rows. For `openIterationEdit(row)`, set a computed or ref `editingRequirementPool` based on `row.is_requirement_pool`. In the existing iteration form, bind `:disabled="editingRequirementPool"` to every non-name control. In `submitIteration`, branch:

```javascript
const payload = editingRequirementPool.value
  ? { name: iterationForm.name.trim() }
  : { ...existingDeliveryPayload }
```

Do not render workflow action, defer, or delete controls for the pool row. Remove the requirements-toolbar pool rename dialog and its state/functions once the list edit path owns the workflow.

**Step 4: Run focused tests and build**

Run:

```powershell
cd frontend
npm test -- requirementPoolIterations requirementPoolProjectView workItemEditDialogs
npm run build
```

Expected: PASS and successful build.

**Step 5: Commit**

```powershell
git add frontend/src/views/ProjectDetailView.vue frontend/src/views/requirementPoolProjectView.test.mjs
git commit -m "feat: edit requirement pools from project iterations"
```

### Task 3: Verify The Full Behavior

**Files:**
- Modify only when verification exposes a defect in files above.

**Step 1: Run full automated checks**

```powershell
cd backend
pytest -q

cd ../frontend
npm test
npm run build
```

Expected: all tests pass; pre-existing dependency/chunk-size warnings may remain during the build.

**Step 2: Verify API and UI semantics**

Start local servers and verify:

1. A project's iteration list places the pool first.
2. The pool edit button opens the standard iteration dialog.
3. Only the name field can be changed for that row.
4. Save renames the pool and the requirement creation selector reflects the new name.
5. A delivery iteration retains normal editing and operations.
6. Global iteration lists and workbench do not show the pool.

**Step 3: Commit verification-only fixes if necessary**

```powershell
git add <verified-files>
git commit -m "fix: close project pool display gaps"
```

Do not create an empty commit.
