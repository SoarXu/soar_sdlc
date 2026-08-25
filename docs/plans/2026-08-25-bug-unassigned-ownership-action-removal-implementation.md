# Bug Unassigned Ownership Action Removal Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Physically remove redundant Bug `transfer` and `change_handler` transitions from every workflow definition's stable `unassigned` state.

**Architecture:** A single idempotent Alembic migration selects exact transition IDs by joining workflow definitions, states and transitions, deletes dependent component routes and role references, then deletes the selected rows. It also removes role references whose transition no longer exists, recovering databases where an earlier delete left them behind. The query is global across Bug workflow origins by explicit product rule; it preserves other object types and ownership actions after assignment.

**Tech Stack:** Python 3, SQLAlchemy, Alembic, pytest.

---

### Task 1: Write the failing deletion-migration test

**Files:**
- Modify: `backend/tests/test_bug_unassigned_ownership_action_recovery_migration.py`

**Step 1: Define the desired database contract**

Create temporary workflow definition, state and transition tables. Seed default-like, imported-like and custom Bug definitions with redundant unassigned actions; also seed Bug `assign`, waiting/active ownership actions and a Task action.

**Step 2: Verify RED**

```powershell
Set-Location backend
& E:\miniforge3\python.exe -m pytest tests/test_bug_unassigned_ownership_action_recovery_migration.py -q
```

Expected: fail because the removal migration does not exist.

### Task 2: Implement the global physical-delete migration

**Files:**
- Create: `backend/alembic/versions/20260824_004_remove_bug_unassigned_ownership_actions.py`
- Test: `backend/tests/test_bug_unassigned_ownership_action_recovery_migration.py`

**Step 1: Select only redundant Bug unassigned actions**

Select transition IDs using these predicates:

```sql
definition.object_type = 'bug'
state.state_role = 'unassigned'
transition.action_key IN ('transfer', 'change_handler')
```

Join the state to the same definition as the transition.

**Step 2: Delete dependencies and selected IDs**

Use SQLAlchemy expanding parameters to delete selected IDs from `business_component_transition_routes`, `workflow_transition_roles`, then `workflow_transitions`. Remove any role references without a matching transition before the empty-selection return, so a database touched by an earlier revision can recover. Keep downgrade non-destructive.

**Step 3: Verify GREEN**

```powershell
Set-Location backend
& E:\miniforge3\python.exe -m pytest tests/test_bug_unassigned_ownership_action_recovery_migration.py -q -rA
```

Expected: default, imported and custom Bug actions are removed; `assign`, later-state actions and Task actions remain; component routes and role references are cleaned; a second run has no effect.

### Task 3: Upgrade and document verification

**Files:**
- Modify after evidence: `docs/issues/2026-08-22-后续问题清单.md`

**Step 1: Reapply the final revision locally**

```powershell
Set-Location backend
& E:\miniforge3\python.exe -m alembic downgrade 20260824_003
& E:\miniforge3\python.exe -m alembic upgrade head
& E:\miniforge3\python.exe -m alembic current
& E:\miniforge3\python.exe -m alembic heads
```

**Step 2: Run focused verification**

```powershell
& E:\miniforge3\python.exe -m pytest tests/test_bug_unassigned_ownership_action_recovery_migration.py tests/test_bug_workflow_action_alignment_migration.py tests/test_default_workflow_templates_api.py -q
& E:\miniforge3\python.exe -m compileall app -q
```

**Step 3: Record evidence**

Update N-004 with the physical deletion rule, global scope, dependency cleanup, migration revision and verification output. Do not commit or push without delivery confirmation.
