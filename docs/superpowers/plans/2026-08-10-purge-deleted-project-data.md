# Purge Deleted Project Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permanently remove deleted-project business data while retaining project tombstones and protecting active/shared data.

**Architecture:** Add a self-contained, idempotent SQLAlchemy Core data migration for historical rows and an ORM service for future project deletions. Both use the same ownership and iteration-safety rules, while the migration remains independent of mutable application code.

**Tech Stack:** Python 3, FastAPI, SQLAlchemy ORM/Core, Alembic, pytest, MySQL, SQLite.

---

### Task 1: Specify Historical Purge Behavior

**Files:**
- Create: `backend/tests/test_purge_deleted_project_data_migration.py`
- Create later: `backend/alembic/versions/20260810_001_purge_deleted_project_data.py`

- [ ] **Step 1: Create the migration loader and SQLite schema**

  Dynamically import revision `20260810_001`, enable `PRAGMA foreign_keys=ON`,
  and create the minimal project, work-item, association, notification,
  component, and iteration tables required by the purge algorithm. Include the
  two production `RESTRICT` edges from projects and requirements to iterations,
  plus the component assignment edge.

- [ ] **Step 2: Seed deleted and active control graphs**

  Seed one deleted project and one active project, each with all five work-item
  types and representative association rows. Seed one deleted-project-only
  iteration, one shared iteration, one active-project-only pool, and one
  unrelated unscoped iteration. Include an active work item whose
  `source_project_id` points at the deleted project, an active row with a bare
  reference to a deleted work item, and an active-project component sourced
  from the deleted project.

- [ ] **Step 3: Assert the complete contract**

  Call `_purge_deleted_project_data(bind)` twice. Assert deleted-owned rows and
  associations are absent, the project tombstone remains with a null pool
  pointer, active/source-only work items remain, bare references are cleared,
  source components and their bindings are removed, shared membership is
  reduced to the active project, unrelated iterations remain, and the second
  report contains only zero counts. Assert `20260810_001 -> 20260806_002`
  revision linkage.

- [ ] **Step 4: Run RED verification**

  Run: `pytest -q tests/test_purge_deleted_project_data_migration.py`

  Expected: FAIL because the new migration does not yet exist.

### Task 2: Implement the Historical Purge Migration

**Files:**
- Create: `backend/alembic/versions/20260810_001_purge_deleted_project_data.py`
- Test: `backend/tests/test_purge_deleted_project_data_migration.py`

- [ ] **Step 1: Add portable ID and delete helpers**

  Reflect tables from the supplied connection, materialize integer IDs before
  mutations, delete by bounded `IN` batches, and accumulate deterministic
  per-table counts. Do not commit, disable foreign keys, or use dialect-specific
  join deletes.

- [ ] **Step 2: Purge object graphs in dependency order**

  Discover `projects.deleted = 1`, snapshot all owned object IDs and candidate
  iteration IDs, clear surviving bare references, then remove notification
  dependencies, polymorphic tables, execution data, project configuration,
  owned-or-sourced components, and main work-item rows in dependency order.

- [ ] **Step 3: Protect shared iterations and preserve tombstones**

  Remove deleted-project membership, null deleted project pool pointers, and
  delete only candidate iterations with no active membership, active pool
  pointer, or active-project work-item reference. Leave every `projects` row.

- [ ] **Step 4: Make upgrade observable and downgrade explicit**

  Have `upgrade()` print a sorted JSON report. Keep `downgrade()` as an explicit
  no-op because physically deleted business and audit data cannot be rebuilt.

- [ ] **Step 5: Run GREEN verification**

  Run: `pytest -q tests/test_purge_deleted_project_data_migration.py`

  Expected: PASS, including the second-run zero-count assertion.

### Task 3: Specify Future Project-Delete Behavior

**Files:**
- Modify: `backend/tests/test_program_project_api.py`
- Create later: `backend/app/services/project_data_purge_service.py`
- Modify later: `backend/app/services/project_service.py`

- [ ] **Step 1: Strengthen the project-tree deletion test**

  After the existing DELETE request, use `SessionLocal` to assert the parent and
  child requirements, task, bug, test case, test run, execution row, and run-case
  row no longer exist. Assert their delivery and requirement-pool iterations no
  longer exist. Assert both project tombstones remain, are deleted, and have
  null pool pointers.

- [ ] **Step 2: Strengthen the shared-iteration test**

  Assert the deleted requirement and deleted project's pool are absent, while
  the active requirement, active project pool, shared iteration, and active
  membership remain. Verify only the deleted project's pool pointer is cleared.

- [ ] **Step 3: Run RED verification**

  Run: `pytest -q tests/test_program_project_api.py -k "project_delete_cascades_project_tree_work_items_and_iterations or project_delete_keeps_shared_iteration_and_removes_deleted_project_scope"`

  Expected: FAIL because the current implementation only soft-deletes work
  items and iterations.

### Task 4: Implement Future Transactional Purging

**Files:**
- Create: `backend/app/services/project_data_purge_service.py`
- Modify: `backend/app/services/project_service.py`
- Test: `backend/tests/test_program_project_api.py`

- [ ] **Step 1: Implement a no-commit purge service**

  Add `purge_project_data(db: Session, project_ids: set[int]) -> dict[str, int]`.
  Materialize all ID sets first, delete dependent and polymorphic rows using ORM
  bulk deletes, remove owned main rows, synchronize project pool-pointer updates,
  and protect iterations referenced by non-target active projects.

- [ ] **Step 2: Replace the soft-delete cascade**

  In `delete_project`, collect the active project tree, call
  `purge_project_data`, then mark only those project objects deleted. Retain one
  final `db.commit()` and remove the obsolete work-item soft-delete helpers.

- [ ] **Step 3: Run focused GREEN verification**

  Run the two-test command from Task 3.

  Expected: both tests PASS with database-level hard-delete assertions.

- [ ] **Step 4: Run related regression tests**

  Run: `pytest -q tests/test_program_project_api.py tests/test_project_work_pool_backfill_migration.py tests/test_purge_deleted_project_data_migration.py`

  Expected: PASS with no failures.

### Task 5: Validate the Real Database and Full Backend

**Files:**
- Modify: no additional source files expected

- [ ] **Step 1: Check migration topology and syntax**

  Run: `python -m alembic -c alembic.ini heads`

  Expected: one head, `20260810_001`.

- [ ] **Step 2: Run the complete backend suite**

  Run: `pytest -q`

  Expected: all tests pass; allow at least 300 seconds because the baseline suite
  exceeded the earlier 120-second window without reporting failures.

- [ ] **Step 3: Apply the migration**

  Run: `python -m alembic -c alembic.ini upgrade head`

  Expected: the JSON purge report is printed and the database reaches
  `20260810_001`.

- [ ] **Step 4: Query post-migration invariants**

  Verify that every deleted project has zero owned requirements, tasks, bugs,
  test cases, test runs, memberships, scope rows, and polymorphic associations;
  verify no deleted project retains a requirement-pool pointer; verify active
  project rows and shared iterations are unchanged.

- [ ] **Step 5: Recheck the original workbench failure**

  Execute the batch transition-options request for the previously affected
  workbench objects and confirm it no longer returns
  `409 REQUIREMENT_POOL_INTEGRITY_ERROR`.

- [ ] **Step 6: Request delivery selection**

  Report code changes, test counts, migration output, and residual counts. Do
  not stage, commit, push, create a PR, or merge until the required delivery
  option is explicitly selected.
