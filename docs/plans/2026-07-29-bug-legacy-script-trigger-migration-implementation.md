# Bug Legacy Script Trigger Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Remove the empty unsupported `legacy_script` trigger from the enabled default Bug workflow without changing its transition behavior.

**Architecture:** Add one idempotent Alembic data migration after revision `20260729_001`. It will clear only `workflow_transitions.trigger_config` for the known empty legacy trigger on definition `#33`; all states, transition IDs, permissions, handler rules, and action names stay intact. Existing API validation already rejects unsupported new automation types, so no runtime or frontend behavior change is needed.

**Tech Stack:** Alembic, SQLAlchemy, Pytest, MySQL-compatible JSON columns.

---

### Task 1: Add a regression test for targeted legacy-trigger cleanup

**Files:**
- Create: `backend/tests/test_legacy_bug_trigger_migration.py`
- Create: `backend/alembic/versions/20260729_002_remove_legacy_bug_trigger.py`

**Step 1: Write the failing test**

Load the migration module with `importlib.util.spec_from_file_location`. Exercise a pure statement-builder/helper against a SQLite fixture containing transition `#136` with `{ "type": "legacy_script" }`, a supported notification trigger, and a different legacy trigger. Assert only `#136` becomes `NULL`.

```python
assert cleaned[136] is None
assert cleaned[137] == {"type": "notification", "receiver": "actor", "title": "Kept"}
assert cleaned[999] == {"type": "legacy_script"}
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_legacy_bug_trigger_migration.py -q`

Expected: FAIL because the migration module/helper does not exist.

**Step 3: Implement the idempotent migration**

Create revision `20260729_002` with `down_revision = "20260729_001"`. In `upgrade()`, clear `trigger_config` only where the transition is ID `136`, belongs to Bug definition `33`, and its JSON type is `legacy_script`. `downgrade()` remains a no-op because the removed marker has no recoverable business payload.

```python
UPDATE workflow_transitions
SET trigger_config = NULL
WHERE id = 136
  AND definition_id = 33
  AND JSON_UNQUOTE(JSON_EXTRACT(trigger_config, '$.type')) = 'legacy_script'
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_legacy_bug_trigger_migration.py -q`

Expected: PASS.

### Task 2: Verify migration behavior and affected workflows

**Files:**
- Test: `backend/tests/test_legacy_bug_trigger_migration.py`
- Test: `backend/tests/test_workflow_definition_api.py`

**Step 1: Run focused backend verification**

Run: `python -m pytest tests/test_legacy_bug_trigger_migration.py tests/test_workflow_definition_api.py -q`

Expected: PASS.

**Step 2: Apply the migration to the configured local database**

Run: `alembic upgrade head`

Expected: revision `20260729_002` applies successfully and transition `#136` has `trigger_config = NULL`.

**Step 3: Verify the persisted target row**

Run a read-only SQL query for transition `#136`.

```sql
SELECT id, definition_id, trigger_config
FROM workflow_transitions
WHERE id = 136;
```

Expected: `136 | 33 | NULL`.

**Step 4: Commit**

```bash
git add backend/alembic/versions/20260729_002_remove_legacy_bug_trigger.py backend/tests/test_legacy_bug_trigger_migration.py docs/plans/2026-07-29-bug-legacy-script-trigger-migration-implementation.md
git commit -m "fix: remove legacy bug workflow trigger"
```
