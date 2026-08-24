# 缺陷工作流确认动作去重实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use `executing-plans` to implement this plan task-by-task.

**Goal:** Eliminate duplicate enabled Bug `confirm_bug_type` transitions from system-managed workflow graphs so administrators can save those graphs safely.

**Architecture:** Extend the existing N-004 managed Bug reconciliation routine with a deterministic single-action invariant. The routine retains the oldest active-work confirmation transition, normalizes it through the existing template upsert, and disables later duplicates. A new Alembic data migration invokes that same idempotent routine for deployed databases.

**Tech Stack:** Python, FastAPI, SQLAlchemy, Alembic, pytest, MySQL.

---

### Task 1: Specify the historical duplicate regression

**Files:**

- Modify: `backend/tests/test_bug_workflow_action_alignment_migration.py`

1. Add a failing test that creates a managed Bug definition with N-002 state roles and two enabled `confirm_bug_type` transitions from `active_work`.
2. Assert the first reconciliation retains exactly one enabled transition, keeps the lower-ID record, applies the standard confirmation action configuration, and disables the duplicate without setting `auto_disabled_by_state`.
3. Invoke reconciliation a second time and assert it returns no change and still has exactly one enabled confirmation action.
4. Run `pytest tests/test_bug_workflow_action_alignment_migration.py -q` serially and verify the new assertion fails before implementation.

### Task 2: Enforce the confirmation-action singleton

**Files:**

- Modify: `backend/app/services/default_workflow_template_service.py`
- Modify: `backend/tests/test_bug_workflow_action_alignment_migration.py`

1. Add a focused helper that queries active-work `confirm_bug_type` transitions in deterministic ID order for one managed definition.
2. Leave the earliest record as the canonical action and set every later duplicate to `enabled=False` and `auto_disabled_by_state=False`.
3. Invoke the helper after legacy confirmation movement and before the existing template upsert; retain the server-side graph duplicate-name validator unchanged.
4. Run the focused regression again and verify it passes; run it a second time to prove idempotence.

### Task 3: Repair deployed data through Alembic

**Files:**

- Create: `backend/alembic/versions/20260824_001_deduplicate_bug_confirmation_transitions.py`
- Modify: `backend/tests/test_bug_workflow_action_alignment_migration.py`

1. Add a test that verifies revision ID `20260824_001`, dependency on `20260822_006`, and use of `reconcile_managed_bug_action_matrices`.
2. Run the focused test and verify it fails because the migration does not exist.
3. Add an upgrade migration that opens a SQLAlchemy session bound to Alembic, calls the shared reconciliation function, commits, and leaves downgrade non-destructive.
4. Run `alembic heads` and verify only `20260824_001` is reported.

### Task 4: Validate graph persistence and regressions

**Files:**

- Modify: `backend/tests/test_bug_workflow_action_alignment_migration.py`
- Modify: `docs/issues/2026-08-22-后续问题清单.md`
- Modify: `docs/plans/2026-08-22-bug-workflow-transition-deduplication-validation.md`

1. Add an API regression test that saves a graph returned after reconciliation and verifies success rather than `422 Duplicate enabled transition name for source state`.
2. Run the new test first to demonstrate the pre-fix failure path, then rerun after the implementation.
3. Run serial focused regression suites: Bug action alignment migration, workflow definition API, default template API, and Bug workflow API.
4. Run `python -m compileall -q app`, `alembic upgrade head`, `alembic current`, and `git diff --check`.
5. Update N-008 with exact results only after the commands pass. Do not commit, push, create a PR, merge, or restart services without explicit user delivery confirmation.
