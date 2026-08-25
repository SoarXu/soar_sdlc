# System Template Graph Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Synchronize the current default workflow scheme into the persisted system templates once, then make workflow template application clone the persisted system graph including layout and routes.

**Architecture:** A shared graph-copy service updates the existing system template records in place by stable state and transition identities. A data migration invokes that service for the four core object types. The workflow designer preview and direct apply endpoints construct their payloads from the same persisted system definition, remapping state references to the target graph without invoking the static code graph.

**Tech Stack:** Python 3, SQLAlchemy, Alembic, FastAPI, pytest, Vue 3.

---

### Task 1: Define regression contracts for system-template synchronization

**Files:**
- Modify: `backend/tests/test_workflow_definition_api.py`
- Modify: `backend/tests/test_assignee_rule_config_api.py`

**Step 1: Write a failing template-preview test**

Create a default-scheme requirement graph with source-only node coordinates and a manual transition route. Request a template preview for another requirement definition. Assert that preview states use the system template graph after synchronization, not `graph_for_object_type()`, and that the route configuration is unchanged.

**Step 2: Write a failing data-migration test**

Seed a default scheme and its system template with matching semantic states but different coordinates and transition configuration. Run the migration upgrade against the fixture. Assert that the system template now equals the default scheme while retaining its state IDs.

**Step 3: Verify RED**

Run: `E:\miniforge3\python.exe -m pytest tests/test_workflow_definition_api.py tests/test_assignee_rule_config_api.py -q`

Expected: the new assertions fail because preview uses `graph_for_object_type()` and no synchronization migration exists.

### Task 2: Add persisted-system-template graph construction

**Files:**
- Modify: `backend/app/services/workflow_definition_service.py`
- Test: `backend/tests/test_workflow_definition_api.py`

**Step 1: Load the system definition deterministically**

Select the enabled definition with `scope_type='system'`, `is_default_template=true`, and the target object type. Raise a clear conflict when it is missing or ambiguous.

**Step 2: Build a target payload from a persisted definition**

Map source states to matching target states by state role first and name/category second, with a legacy fallback for targets that have not yet stored a state role. Copy all state fields including `x`, `y`, and `sort_order`; reuse matching transition IDs by action key and mapped endpoints, map conditional state references to target IDs, and preserve role references and `diagram_config`.

**Step 3: Point preview and direct apply to this payload**

Replace the static `graph_for_object_type()` source in both functions. Keep preview non-persistent and direct apply persistent.

**Step 4: Verify GREEN**

Run: `E:\miniforge3\python.exe -m pytest tests/test_workflow_definition_api.py -q`

Expected: previews and direct application reproduce persisted system-template state positions, transitions and routes.

### Task 3: Synchronize the default scheme into system templates once

**Files:**
- Modify: `backend/app/services/assignee_rule_config_service.py`
- Create: `backend/alembic/versions/20260825_001_sync_default_scheme_graphs_to_system_templates.py`
- Test: `backend/tests/test_assignee_rule_config_api.py`

**Step 1: Write the failing in-place synchronization test**

Create matching source and system graphs with distinct coordinates, transition configuration and system-state references. Assert source values overwrite target graph fields but target state IDs remain unchanged.

**Step 2: Implement in-place synchronization**

Use state role, name/category and structural fallback identities only when a candidate is unique. Create source-only states/transitions, disable target-only historical states/transitions, and preserve IDs for matched records. Group transitions by action key and source state, pair matching target states before deterministic enabled/sort/ID fallback, then update state and transition fields in place. Replace transition role references, remap condition state IDs, and do not schedule future synchronization.

**Step 3: Add the Alembic migration**

Locate the enabled “默认工作流规则” and its four core workflow definitions, locate the four system templates, synchronize each graph, and commit as one migration transaction. Raise a descriptive error if a source is missing or inconsistent.

**Step 4: Verify GREEN**

Run: `E:\miniforge3\python.exe -m pytest tests/test_assignee_rule_config_api.py -q`

Expected: system templates receive the complete graph once; later source edits leave them unchanged.

### Task 4: Validate and record evidence

**Files:**
- Modify: `docs/issues/2026-08-22-后续问题清单.md`

**Step 1: Reapply the migration locally**

Run:

```powershell
Set-Location backend
& E:\miniforge3\python.exe -m alembic upgrade head
& E:\miniforge3\python.exe -m alembic current
& E:\miniforge3\python.exe -m alembic heads
```

**Step 2: Run focused regression and build checks**

Run:

```powershell
& E:\miniforge3\python.exe -m pytest tests/test_workflow_definition_api.py tests/test_assignee_rule_config_api.py tests/test_default_workflow_templates_api.py -q
& E:\miniforge3\python.exe -m compileall app -q
Set-Location ..\frontend
npm run build
```

**Step 3: Record results**

Update N-010 with source/destination boundaries, migration revision and observed verification results. Do not commit, push or merge without delivery confirmation.

## Execution Evidence

- Added Alembic revision `20260825_001`, which invokes the one-time graph synchronization after `20260824_004` in one transaction without running startup reconciliation against the source graph.
- The local database reports `20260825_001 (head)` and its only head is `20260825_001`.
- A final idempotent synchronization copied all four current default-rule graphs. Normalized source/system comparisons were equal for requirement (`7` states, `25` transitions), task (`7`, `26`), Bug (`7`, `35`) and project (`4`, `6`).
- Target system state and transition records are updated in place when uniquely matched, while source-only graph elements are created and target-only historical elements are disabled. Repeated template application reuses transition IDs. New cloned scheme definitions clear `parent_definition_id` so graph copies have no source dependency.
- Regression coverage now includes repeated template application, missing state-role fallback, source graph additions/removals, duplicate-action target matching and transactional template initialization. The four focused backend suites pass `88` tests; backend compilation and frontend production build pass.
