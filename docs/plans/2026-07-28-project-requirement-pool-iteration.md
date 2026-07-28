# Project Requirement Pool Iteration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure every requirement always belongs to either its project's system-managed requirement pool or a delivery iteration, while keeping requirement pools out of normal iteration execution and reporting.

**Architecture:** Add a read-only `iterations.is_requirement_pool` identity and a canonical `projects.requirement_pool_iteration_id` reference. Create the pool transactionally with each project, resolve omitted requirement iterations to that pool in one domain service, and protect the pool by ID/flag rather than name. Backfill every existing project and requirement before making `requirements.iteration_id` non-null.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic, MySQL/SQLite test fixtures, Vue 3, Element Plus, Node-based frontend source tests, pytest.

---

Implementation must follow @superpowers:test-driven-development for every behavior change and @superpowers:verification-before-completion before reporting success. Work in a dedicated worktree when executing this plan; this planning session remained on `main` because the design discussion and documentation were already in the shared workspace.

### Task 1: Add the migration contract and ORM fields

**Files:**
- Create: `backend/alembic/versions/20260728_001_project_requirement_pool_iterations.py`
- Create: `backend/tests/test_requirement_pool_iteration_migration.py`
- Modify: `backend/app/models/iteration.py`
- Modify: `backend/app/models/project.py`
- Modify: `backend/app/models/requirement.py`
- Modify: `backend/app/views/iteration_view.py`
- Modify: `backend/app/views/project_view.py`

**Step 1: Write failing migration and metadata tests**

Add tests that assert:

```python
def test_requirement_pool_columns_are_registered_in_model_metadata():
    assert Iteration.__table__.c.is_requirement_pool.nullable is False
    assert Project.__table__.c.requirement_pool_iteration_id.nullable is True
    assert Requirement.__table__.c.iteration_id.nullable is False


def test_migration_has_deterministic_integrity_audit():
    migration = _migration_module()
    issues = [
        {"issue": "missing_pool_reference", "ids": [9, 2]},
        {"issue": "null_requirement_iteration", "ids": [7]},
    ]
    assert migration._format_audit_issues(issues) == (
        "Requirement pool migration audit failed: "
        "missing_pool_reference=2,9; null_requirement_iteration=7"
    )
```

Also assert the migration revision is `20260728_001`, its parent is `20260727_001`, and its audit checks missing project references, wrong pool flags, pool-to-project scope mismatches, null requirement iteration IDs, and dangling requirement iteration references.

**Step 2: Run the tests to verify they fail**

Run:

```powershell
cd backend
pytest tests/test_requirement_pool_iteration_migration.py -q
```

Expected: FAIL because the migration and model columns do not exist.

**Step 3: Implement the model and response fields**

Add:

```python
# Iteration
is_requirement_pool: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

# Project
requirement_pool_iteration_id: Mapped[int | None] = mapped_column(
    BigInteger,
    ForeignKey("iterations.id", ondelete="RESTRICT", use_alter=True),
    nullable=True,
    unique=True,
)

# Requirement
iteration_id: Mapped[int] = mapped_column(
    BigInteger,
    ForeignKey("iterations.id", ondelete="RESTRICT"),
    nullable=False,
)
```

Expose `is_requirement_pool: bool` only on `IterationRead`, expose `requirement_pool_iteration_id: int | None` only on `ProjectRead`, and override `RequirementRead.iteration_id` as non-null `int` while keeping create/update input compatible with omitted/null values. Do not add either system identity field to create/update iteration or project request models.

**Step 4: Implement the Alembic migration**

The upgrade must:

1. Add `iterations.is_requirement_pool` as non-null with server default `0`.
2. Add nullable `projects.requirement_pool_iteration_id`.
3. Resolve the latest enabled default system iteration workflow and its enabled initial state; fail with a deterministic diagnostic if unavailable.
4. Create one pool iteration for every project, including soft-deleted historical projects. Copy the project lifecycle phase, use name `需求池`, leave dates/owner/goal empty, set the pool's deleted fields consistently for deleted projects, and insert exactly one `iteration_projects` row.
5. Update each project's canonical pool reference.
6. Move every requirement with null `iteration_id` to its project's pool.
7. Run `_audit_or_raise(bind)` before tightening constraints.
8. Add the unique project reference constraint and both foreign keys.
9. Alter `requirements.iteration_id` to non-null.

Use parameterized SQLAlchemy statements, not string-built ID lists. Downgrade must refuse to proceed when a requirement currently points to a pool unless it first converts those rows to null; then drop constraints and columns in dependency order.

**Step 5: Run focused tests**

Run:

```powershell
cd backend
pytest tests/test_requirement_pool_iteration_migration.py tests/test_project_iteration_state_migration.py -q
```

Expected: PASS.

**Step 6: Commit**

```powershell
git add backend/alembic/versions/20260728_001_project_requirement_pool_iterations.py backend/tests/test_requirement_pool_iteration_migration.py backend/app/models/iteration.py backend/app/models/project.py backend/app/models/requirement.py backend/app/views/iteration_view.py backend/app/views/project_view.py
git commit -m "feat: add project requirement pool identity"
```

### Task 2: Build the requirement-pool domain service and transactional project creation

**Files:**
- Create: `backend/app/services/requirement_pool_service.py`
- Create: `backend/tests/test_requirement_pool_iteration_api.py`
- Modify: `backend/app/services/project_service.py`

**Step 1: Write failing project creation tests**

Cover these assertions:

```python
def test_project_creation_builds_one_canonical_requirement_pool(client):
    project = client.post("/api/v1/projects", json={"name": "Pool project"}).json()
    pool = client.get(
        "/api/v1/iterations",
        params={"project_id": project["id"], "include_requirement_pool": True},
    ).json()
    pool = next(item for item in pool if item["is_requirement_pool"])
    assert project["requirement_pool_iteration_id"] == pool["id"]
    assert pool["name"] == "需求池"
    assert pool["project_ids"] == [project["id"]]


def test_project_creation_rolls_back_when_pool_creation_fails(client, monkeypatch):
    monkeypatch.setattr(project_service, "create_project_requirement_pool", _raise)
    response = client.post("/api/v1/projects", json={"name": "Atomic project"})
    assert response.status_code == 409
    assert SessionLocal().query(Project).filter(Project.name == "Atomic project").count() == 0
```

Also assert ordinary iteration creation always returns `is_requirement_pool is False`, even if the client submits an extra `is_requirement_pool` key.

**Step 2: Run the tests to verify they fail**

Run:

```powershell
cd backend
pytest tests/test_requirement_pool_iteration_api.py -q
```

Expected: FAIL because projects do not yet create pools.

**Step 3: Implement a single pool domain service**

Create small, explicit functions:

```python
POOL_INTEGRITY_ERROR = "REQUIREMENT_POOL_INTEGRITY_ERROR"

def create_project_requirement_pool(db: Session, project: Project) -> Iteration:
    workflow = initial_system_workflow_values(db, "iteration")
    pool = Iteration(
        name="需求池",
        is_requirement_pool=True,
        lifecycle_phase=project_lifecycle_phase(db, project.id),
        **workflow,
    )
    db.add(pool)
    db.flush()
    db.add(IterationProject(iteration_id=pool.id, project_id=project.id))
    project.requirement_pool_iteration_id = pool.id
    return pool


def requirement_pool_for_project(db: Session, project_id: int, *, for_update=False) -> Iteration:
    # Load the active project, canonical iteration and exact IterationProject row.
    # Return 409 with POOL_INTEGRITY_ERROR if any identity invariant is broken.
```

Do not implement runtime get-or-create behavior. Missing or inconsistent references are integrity failures.

**Step 4: Make project creation atomic**

Replace the early commit in `create_project` with:

```python
db.add(project)
db.flush()
create_project_requirement_pool(db, project)
db.commit()
db.refresh(project)
```

Rollback and re-raise on any exception. Ensure the project response contains the pool reference.

**Step 5: Run focused tests**

Run:

```powershell
cd backend
pytest tests/test_requirement_pool_iteration_api.py tests/test_program_project_api.py -q
```

Expected: PASS.

**Step 6: Commit**

```powershell
git add backend/app/services/requirement_pool_service.py backend/app/services/project_service.py backend/tests/test_requirement_pool_iteration_api.py
git commit -m "feat: create requirement pool with each project"
```

### Task 3: Route all requirement creation and editing through the pool

**Files:**
- Modify: `backend/app/services/requirement_pool_service.py`
- Modify: `backend/app/services/requirement_service.py`
- Modify: `backend/app/services/requirement_import_service.py`
- Modify: `backend/tests/test_requirement_pool_iteration_api.py`
- Modify: `backend/tests/test_requirement_import_api.py`
- Modify: `backend/tests/test_requirement_task_api.py`

**Step 1: Write failing requirement assignment tests**

Add tests for:

- omitted and explicit-null `iteration_id` both resolve to the canonical pool;
- explicitly selected delivery iteration remains selected;
- a pool belonging to another project is rejected;
- clearing a delivery iteration moves the requirement to the pool and creates a new open history row;
- changing project while in the old pool moves to the new pool;
- changing project while in a compatible delivery iteration keeps the delivery iteration;
- changing project while in an incompatible delivery iteration returns 400;
- imported new requirements enter the pool;
- duplicate import updates retain the existing formal iteration instead of clearing it.

Use assertions such as:

```python
assert created["iteration_id"] == project["requirement_pool_iteration_id"]
assert updated["iteration_id"] == target_project["requirement_pool_iteration_id"]
assert [row.enter_reason for row in histories] == ["created", "updated"]
```

**Step 2: Run the tests to verify they fail**

Run:

```powershell
cd backend
pytest tests/test_requirement_pool_iteration_api.py tests/test_requirement_import_api.py tests/test_requirement_task_api.py -q
```

Expected: FAIL on null iteration expectations and import behavior.

**Step 3: Add canonical resolution helpers**

Implement:

```python
def resolve_requirement_iteration_id(
    db: Session,
    project_id: int,
    requested_iteration_id: int | None,
) -> int:
    if requested_iteration_id is None:
        return requirement_pool_for_project(db, project_id).id
    _ensure_requirement_iteration_scope(db, project_id, requested_iteration_id)
    return requested_iteration_id
```

When an explicitly selected iteration is a pool, verify it is exactly the project's canonical pool. Do not accept a flagged but non-canonical pool.

**Step 4: Update create and patch paths**

In `create_requirement`, resolve the iteration before `ensure_iteration_assignment_mutable`. Always call `move_work_item_to_iteration(..., reason="created")` after the requirement is flushed.

In `update_requirement`, derive the target in this order:

```python
target_project_id = data.get("project_id", requirement.project_id)
iteration_was_supplied = "iteration_id" in data
requested_iteration_id = data.get("iteration_id") if iteration_was_supplied else requirement.iteration_id

if target_project_id != requirement.project_id and is_project_requirement_pool(
    db, requirement.project_id, requirement.iteration_id
):
    requested_iteration_id = None

target_iteration_id = resolve_requirement_iteration_id(db, target_project_id, requested_iteration_id)
```

Move membership whenever the resolved ID changes, even if the client supplied null. Preserve existing iteration history locking.

**Step 5: Update import behavior**

For new rows, resolve the project pool ID and create/open membership history consistently. For duplicate updates, stop calling `move_work_item_to_iteration(..., None)`: imports do not carry an iteration column, so they must preserve the existing membership.

Update pre-lock collection so pool IDs are locked like any other current requirement iteration.

**Step 6: Run focused tests**

Run:

```powershell
cd backend
pytest tests/test_requirement_pool_iteration_api.py tests/test_requirement_import_api.py tests/test_requirement_task_api.py tests/test_work_item_iteration_history.py -q
```

Expected: PASS.

**Step 7: Commit**

```powershell
git add backend/app/services/requirement_pool_service.py backend/app/services/requirement_service.py backend/app/services/requirement_import_service.py backend/tests/test_requirement_pool_iteration_api.py backend/tests/test_requirement_import_api.py backend/tests/test_requirement_task_api.py backend/tests/test_work_item_iteration_history.py
git commit -m "feat: keep requirements assigned to an iteration"
```

### Task 4: Replace iteration unlink and available-requirement semantics

**Files:**
- Modify: `backend/app/services/iteration_service.py`
- Modify: `backend/tests/test_iteration_detail_api.py`
- Modify: `backend/tests/test_work_item_iteration_history.py`

**Step 1: Write failing iteration membership tests**

Change old assertions that expected `Requirement.iteration_id is None`. Add tests proving:

- a project's pool requirement appears in another compatible delivery iteration's available-requirements list;
- pool requirements outside the target iteration's project scope do not appear;
- linking a pool requirement moves it to the delivery iteration;
- linking a requirement already in another delivery iteration remains rejected;
- unlinking from a delivery iteration moves it to its canonical project pool;
- history closes the delivery row and opens a pool row with `enter_reason == "unlinked"`.

**Step 2: Run the tests to verify they fail**

Run:

```powershell
cd backend
pytest tests/test_iteration_detail_api.py tests/test_work_item_iteration_history.py -q
```

Expected: FAIL because available requirements still query null and unlink still writes null.

**Step 3: Change the available query**

Replace `Requirement.iteration_id.is_(None)` with a join against the canonical project pool:

```python
db.query(Requirement)
  .join(Project, Project.id == Requirement.project_id)
  .filter(
      Requirement.deleted == 0,
      Requirement.project_id.in_(scoped_project_ids),
      Requirement.iteration_id == Project.requirement_pool_iteration_id,
  )
```

**Step 4: Change link and unlink behavior**

Allow `link_requirements` when the source iteration is the requirement project's canonical pool; retain rejection for a different delivery iteration. In `unlink_requirement`, resolve the canonical project pool and move there instead of passing `None`.

Keep all movement through `move_work_item_to_iteration` so close/open history rows remain atomic.

**Step 5: Run focused tests**

Run:

```powershell
cd backend
pytest tests/test_iteration_detail_api.py tests/test_work_item_iteration_history.py -q
```

Expected: PASS.

**Step 6: Commit**

```powershell
git add backend/app/services/iteration_service.py backend/tests/test_iteration_detail_api.py backend/tests/test_work_item_iteration_history.py
git commit -m "feat: return removed requirements to project pools"
```

### Task 5: Protect requirement pools while allowing rename

**Files:**
- Modify: `backend/app/services/iteration_service.py`
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/controllers/iteration_controller.py`
- Modify: `backend/tests/test_requirement_pool_iteration_api.py`
- Modify: `backend/tests/test_workflow_runtime_api.py`

**Step 1: Write failing protection tests**

Cover:

- patching only `name` succeeds for project managers/admins and preserves the flag/reference;
- patching owner, dates, goal, lifecycle phase or project IDs returns 409 with `REQUIREMENT_POOL_OPERATION_FORBIDDEN`;
- delete, detail, defer, available/link task/requirement management, and direct workflow transition endpoints reject the pool;
- available workflow actions for a pool are an empty list;
- normal delivery iterations retain all current operations;
- rename produces an audit entry containing old and new names.

**Step 2: Run the tests to verify they fail**

Run:

```powershell
cd backend
pytest tests/test_requirement_pool_iteration_api.py tests/test_workflow_runtime_api.py -q
```

Expected: FAIL because pools are currently treated as ordinary iterations.

**Step 3: Add a dedicated iteration-operation guard**

Do not make `ensure_iteration_mutable` reject pools, because requirement membership must still move into and out of a pool. Add a separate guard:

```python
def ensure_delivery_iteration(iteration: Iteration) -> None:
    if iteration.is_requirement_pool:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "REQUIREMENT_POOL_OPERATION_FORBIDDEN",
                "message": "Requirement pool does not support this iteration operation",
            },
        )
```

Call it from delivery-iteration-only operations. In `update_iteration`, special-case pools before the normal update path: accept only a nonblank changed `name`, add `AuditLog(object_type="iteration", action="update", ...)`, and reject every other supplied field.

**Step 4: Guard workflow discovery and execution**

In `list_available_transitions`, return `[]` for an iteration pool. In `execute_transition`, after locking the item and before resolving the transition, reject a pool with the stable error code. This protects both direct and batch action paths.

**Step 5: Run focused tests**

Run:

```powershell
cd backend
pytest tests/test_requirement_pool_iteration_api.py tests/test_workflow_runtime_api.py tests/test_iteration_detail_api.py -q
```

Expected: PASS.

**Step 6: Commit**

```powershell
git add backend/app/services/iteration_service.py backend/app/services/workflow_runtime_service.py backend/app/controllers/iteration_controller.py backend/tests/test_requirement_pool_iteration_api.py backend/tests/test_workflow_runtime_api.py
git commit -m "feat: protect system requirement pools"
```

### Task 6: Exclude pools from delivery lists and workbench scope

**Files:**
- Modify: `backend/app/controllers/iteration_controller.py`
- Modify: `backend/app/services/project_service.py`
- Modify: `backend/app/services/dashboard_service.py`
- Modify: `backend/app/services/iteration_service.py`
- Modify: `backend/tests/test_requirement_pool_iteration_api.py`
- Modify: `backend/tests/test_dashboard_workbench_api.py`

**Step 1: Write failing query-scope tests**

Assert:

- `GET /projects/{id}/iterations` does not contain the pool;
- `GET /iterations?project_id=...` excludes the pool by default;
- `GET /iterations?project_id=...&include_requirement_pool=true` contains the pool and exposes its flag for requirement selectors;
- a requirement and an inherited task in the pool do not appear in any normal workbench section;
- a pool never becomes active workbench scope even if its state has outgoing complete/cancel transitions;
- ordinary active iterations remain visible.

**Step 2: Run the tests to verify they fail**

Run:

```powershell
cd backend
pytest tests/test_requirement_pool_iteration_api.py tests/test_dashboard_workbench_api.py -q
```

Expected: FAIL because project iteration pages include all iterations and workbench scope does not explicitly check the flag.

**Step 3: Implement explicit pool exclusions**

Add `Iteration.is_requirement_pool.is_(False)` to `list_project_iterations_page` and `_active_iteration_ids`. Add `include_requirement_pool: bool = False` to the `/iterations` controller and `list_iterations`; apply the false predicate unless the flag is true. Requirement-related pages explicitly opt in, while the global iteration page and Bug/test selectors retain delivery-only defaults. Always serialize `is_requirement_pool` in `_iteration_to_dict` and `list_iterations`.

Audit any completion/statistics queries found by:

```powershell
rg -n "Iteration|iteration_id|iteration_ids" backend/app/services -g "*.py"
```

Add the explicit false predicate wherever a query represents delivery iteration counts, progress, burn-down, or selectable defer targets. Do not exclude pools from requirement label resolution or membership history name resolution.

**Step 4: Run focused tests**

Run:

```powershell
cd backend
pytest tests/test_requirement_pool_iteration_api.py tests/test_dashboard_workbench_api.py tests/test_iteration_detail_api.py -q
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add backend/app/controllers/iteration_controller.py backend/app/services/project_service.py backend/app/services/dashboard_service.py backend/app/services/iteration_service.py backend/tests/test_requirement_pool_iteration_api.py backend/tests/test_dashboard_workbench_api.py
git commit -m "feat: exclude requirement pools from delivery scope"
```

### Task 7: Add tested frontend iteration classification helpers

**Files:**
- Create: `frontend/src/utils/requirementPoolIterations.js`
- Create: `frontend/src/utils/requirementPoolIterations.test.mjs`

**Step 1: Write failing helper tests**

Define behavior for:

```javascript
assert.deepEqual(deliveryIterations(items).map((item) => item.id), [12, 13])
assert.equal(requirementPoolForProject(project, items).id, 11)
assert.deepEqual(requirementIterationOptions(project, projects, items).map((item) => item.id), [11, 12, 13])
assert.equal(requirementIterationLabel(items[0]), '需求池名称（未排期）')
```

Also test missing pool references return `null` rather than selecting an arbitrary flagged pool.

**Step 2: Run the test to verify it fails**

Run:

```powershell
cd frontend
npm test -- requirementPoolIterations
```

Expected: FAIL because the helper does not exist.

**Step 3: Implement minimal pure helpers**

Keep classification in one module:

```javascript
export function deliveryIterations(items = []) {
  return items.filter((item) => !item.is_requirement_pool)
}

export function requirementPoolForProject(project, items = []) {
  return items.find((item) => item.id === project?.requirement_pool_iteration_id && item.is_requirement_pool) || null
}
```

`requirementIterationOptions(project, projects, items)` must return the canonical pool first, followed by delivery iterations whose root projects contain the selected project itself or one of its ancestors. It must exclude every other project's pool, including an ancestor project's pool. Append `（未排期）` only in selector labels; preserve the user-editable stored name.

**Step 4: Run the test**

Run:

```powershell
cd frontend
npm test -- requirementPoolIterations
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add frontend/src/utils/requirementPoolIterations.js frontend/src/utils/requirementPoolIterations.test.mjs
git commit -m "feat: classify requirement pool iterations"
```

### Task 8: Update requirement forms and add pool rename UI

**Files:**
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/views/RequirementsView.vue`
- Modify: `frontend/src/views/RequirementDetailView.vue`
- Modify: `frontend/src/components/work-items/RequirementEditDialog.vue`
- Modify: `frontend/src/components/workItemEditDialogs.test.mjs`
- Create: `frontend/src/views/requirementPoolProjectView.test.mjs`

**Step 1: Write failing source-integration tests**

Assert that all requirement forms use canonical requirement options and never use delivery-only options. Test these source-level contracts:

- project requirement creation initializes `iteration_id` to the project's pool;
- changing the selected project in the global requirements page selects the new project's pool for new records;
- edit/detail dialogs include the canonical pool and delivery iterations for the requirement project;
- requirement iteration selects are not clearable;
- the normal project iteration table does not render a pool row from client-side fallback data;
- the requirements tab exposes a pencil icon button with an accessible tooltip for renaming the pool;
- rename submits only `{ name }` to `updateIteration` and refreshes project/iteration data.

**Step 2: Run tests to verify they fail**

Run:

```powershell
cd frontend
npm test -- requirementPoolProjectView workItemEditDialogs
```

Expected: FAIL on missing helper use and rename behavior.

**Step 3: Update form options and defaults**

Use the shared helpers everywhere. Requirement-related data loads must call `fetchIterations({ include_requirement_pool: true })`; ordinary iteration, Bug and test pages keep the default request. In project detail reset logic:

```javascript
const projectRequirementPool = computed(() => requirementPoolForProject(project.value, iterations.value))

function resetRequirementForm() {
  Object.assign(requirementForm, {
    project_id: projectId.value,
    iteration_id: projectRequirementPool.value?.id ?? null,
    // existing defaults
  })
}
```

In global create, watch the selected `project_id` only when creating, not editing, and set the canonical pool. Remove `clearable` from requirement iteration selectors; the pool is the explicit “not yet scheduled” choice. Continue sending a nullable fallback so older clients remain compatible with the backend resolver.

Set `projectIterationOptions` and delivery-only controls such as defer targets with `deliveryIterations`, because project detail deliberately fetched pools for its requirement form. This prevents the pool from leaking into iteration tables, test/Bug selects, and defer targets.

**Step 4: Add rename interaction**

In the project requirements toolbar, add an Element Plus icon button using the existing icon library and tooltip `重命名需求池`. Show a compact dialog/input initialized to the current pool name. Require a nonblank trimmed name, then call:

```javascript
await updateIteration(projectRequirementPool.value.id, { name: poolName.value.trim() })
```

Use existing `canManageCurrentProject` permissions, loading state and `showActionError`. Do not expose dates, owner, status, goal or project associations.

**Step 5: Run focused frontend tests and build**

Run:

```powershell
cd frontend
npm test -- requirementPoolIterations requirementPoolProjectView workItemEditDialogs
npm run build
```

Expected: all selected tests PASS and Vite build succeeds.

**Step 6: Commit**

```powershell
git add frontend/src/views/ProjectDetailView.vue frontend/src/views/RequirementsView.vue frontend/src/views/RequirementDetailView.vue frontend/src/components/work-items/RequirementEditDialog.vue frontend/src/components/workItemEditDialogs.test.mjs frontend/src/views/requirementPoolProjectView.test.mjs
git commit -m "feat: expose project requirement pools in planning forms"
```

### Task 9: Align the product documentation and data contract

**Files:**
- Modify: `docs/prd/2026-07-21-workbench-active-iteration-scope-prd.md`
- Modify: `docs/database/2026-06-09-intellective-bio-sdlc-data-dictionary-mysql.md`
- Modify: `docs/database/init_mysql.sql`

**Step 1: Add a failing repository contract test or guard**

Extend an existing repository guard test, or add `backend/tests/test_requirement_pool_repository_contract.py`, to assert that active PRD text no longer describes requirements as nullable/uniterated and that schema documentation contains:

```text
iterations.is_requirement_pool
projects.requirement_pool_iteration_id
requirements.iteration_id NOT NULL
```

The PRD may still describe uniterated tasks and Bugs; assertions must distinguish those from requirements.

**Step 2: Run the test to verify it fails**

Run:

```powershell
cd backend
pytest tests/test_requirement_pool_repository_contract.py -q
```

Expected: FAIL on stale PRD/schema text.

**Step 3: Update documentation and bootstrap SQL**

Replace statements saying normal requirements may be uniterated with: requirements in the project pool are excluded from normal workbench sections and are scheduled from project detail. Preserve the rule that being in a pool is not itself an exception.

Update the data dictionary and `init_mysql.sql` with the two new fields, unique/foreign-key constraints, requirement non-null FK, and index definitions. Bootstrap SQL should create schema only; runtime project creation still creates pool rows.

**Step 4: Run the guard**

Run:

```powershell
cd backend
pytest tests/test_requirement_pool_repository_contract.py -q
```

Expected: PASS.

**Step 5: Commit**

```powershell
git add docs/prd/2026-07-21-workbench-active-iteration-scope-prd.md docs/database/2026-06-09-intellective-bio-sdlc-data-dictionary-mysql.md docs/database/init_mysql.sql backend/tests/test_requirement_pool_repository_contract.py
git commit -m "docs: align requirement planning with project pools"
```

### Task 10: Run migration, regression and visual verification

**Files:**
- Modify only if verification exposes a defect in files already named above.

**Step 1: Verify migration heads and isolated upgrade**

Run:

```powershell
cd backend
alembic heads
alembic upgrade head
```

Expected: exactly one head, `20260728_001`, and successful upgrade with no requirement-pool audit errors.

Query the migrated database and verify:

```sql
SELECT COUNT(*) FROM requirements WHERE iteration_id IS NULL;
SELECT COUNT(*) FROM projects WHERE deleted = 0 AND requirement_pool_iteration_id IS NULL;
SELECT COUNT(*)
FROM projects p
JOIN iterations i ON i.id = p.requirement_pool_iteration_id
WHERE i.is_requirement_pool <> 1;
```

Expected: all counts are `0`.

**Step 2: Run the full backend suite**

Run:

```powershell
cd backend
pytest -q
```

Expected: PASS with no failures.

**Step 3: Run the full frontend suite and build**

Run:

```powershell
cd frontend
npm test
npm run build
```

Expected: all frontend tests PASS and production build succeeds.

**Step 4: Run targeted repository searches**

Run:

```powershell
rg -n "Requirement\.iteration_id\.is_\(None\)|requirement\.iteration_id is None|iteration_id=None" backend/app -g "*.py"
rg -n "未关联迭代的正常需求|需求.*iteration_id.*null" docs frontend/src backend/app
```

Expected: no active code path creates or searches for a null requirement iteration; any remaining documentation match is explicitly historical or migration-related.

**Step 5: Visually verify the project workflow**

Start the existing backend and frontend dev servers. Use the in-app browser to verify at desktop and mobile widths:

1. Create a project and confirm the normal iteration list is empty.
2. Open new requirement and confirm the renamed/default pool is selected.
3. Create a delivery iteration, schedule the requirement into it, then remove it and confirm it returns to the pool.
4. Rename the pool and confirm every requirement selector/label updates.
5. Confirm no pool action buttons, detail link or delivery statistics are exposed.
6. Confirm layouts do not overlap and long pool names wrap or truncate predictably.

Capture screenshots as verification artifacts if the repository's existing QA flow expects them; do not commit generated screenshots unless that convention already exists.

**Step 6: Final commit for verification-only fixes**

If verification required changes, rerun the affected focused tests and commit only those fixes:

```powershell
git add <verified-files>
git commit -m "fix: close requirement pool regression gaps"
```

If no fixes were needed, do not create an empty commit.
