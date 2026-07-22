# Batch Work Item Assignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add atomic batch assignment for requirement, task, and bug lists while preserving workflow authorization, routing, logs, and notifications.

**Architecture:** Runtime actions expose server-calculated batch-assignment metadata. The three list views use that metadata with one shared bottom action control. A batch endpoint preflights every item and executes the existing workflow logic once within one transaction.

**Tech Stack:** Vue 3, Element Plus, Axios, FastAPI, Pydantic, SQLAlchemy, pytest, Node assert tests.

**Workspace:** Work in the current main workspace because it contains active user changes. Stage only files named by each task.

---

### Task 1: Define API contracts

**Files:**

- Modify: `backend/app/views/workflow_runtime_view.py`
- Test: `backend/tests/test_workflow_runtime_api.py`

**Step 1: Write failing tests**

Add transition-read assertions for this metadata:

```python
assert action["bulk_assignment"] == {
    "supported": True,
    "requires_delegate_reason": False,
    "eligible_assignee_ids": [developer_id],
}
```

Add a failing POST test for `/api/v1/workflow-runtime/assignments/batch` with an object type, project ID, target handler, optional reason, and `{id, transition_id}` items.

**Step 2: Run it and verify it fails**

Run: `pytest backend/tests/test_workflow_runtime_api.py -k "bulk_assignment" -v`

Expected: FAIL because neither metadata nor route exists.

**Step 3: Implement the Pydantic models**

Add `WorkflowBulkAssignmentMetadata`, `WorkflowBulkAssignmentItem`, `WorkflowBulkAssignmentRequest`, and a response model. The metadata has `supported`, `requires_delegate_reason`, and `eligible_assignee_ids`; add it to `WorkflowTransitionActionRead` with a default value for client compatibility.

**Step 4: Re-run the test**

Run: `pytest backend/tests/test_workflow_runtime_api.py -k "bulk_assignment" -v`

Expected: contract parsing passes; endpoint behavior remains failing until Task 3.

**Step 5: Commit**

Run: `git add backend/app/views/workflow_runtime_view.py backend/tests/test_workflow_runtime_api.py`

Run: `git commit -m "test: define batch assignment runtime contract"`

### Task 2: Expose batch-assignment metadata

**Files:**

- Modify: `backend/app/services/workflow_runtime_service.py:58-99`
- Modify: `backend/app/services/workflow_runtime_service.py:295-345`
- Test: `backend/tests/test_workflow_runtime_api.py`

**Step 1: Write failing metadata tests**

Cover a manually assignable transition, a non-assignment transition, one with custom form fields, and a target-role restriction:

```python
assert assign_action["bulk_assignment"]["supported"] is True
assert assign_action["bulk_assignment"]["eligible_assignee_ids"] == [developer_id]
assert non_assignment_action["bulk_assignment"]["supported"] is False
assert custom_form_action["bulk_assignment"]["supported"] is False
```

Use both developer and tester members to prove `manual_owner_roles` is enforced.

**Step 2: Run it and verify it fails**

Run: `pytest backend/tests/test_workflow_runtime_api.py -k "bulk_assignment_metadata" -v`

Expected: FAIL because `_transition_read` has no metadata.

**Step 3: Implement the metadata helper**

Add a private helper adjacent to `_transition_read`. It receives item, transition, and actor. It supports batch assignment only when the transition is available, `allow_manual_owner` is true, no custom fields or target-state selection is required, and the item project is active. Query `ProjectMember` using `manual_owner_roles` and return only users accepted by `_ensure_manual_owner_allowed`. Reuse delegated-execution logic for `requires_delegate_reason`.

Pass the helper result into the transition read response; update callers to pass item and actor.

**Step 4: Run it and verify it passes**

Run: `pytest backend/tests/test_workflow_runtime_api.py -k "bulk_assignment_metadata" -v`

Expected: PASS.

**Step 5: Commit**

Run: `git add backend/app/services/workflow_runtime_service.py backend/tests/test_workflow_runtime_api.py`

Run: `git commit -m "feat: expose batch assignment transition metadata"`

### Task 3: Add atomic batch workflow execution

**Files:**

- Modify: `backend/app/controllers/workflow_runtime_controller.py`
- Modify: `backend/app/services/workflow_runtime_service.py:103-241`
- Modify: `backend/app/views/workflow_runtime_view.py`
- Test: `backend/tests/test_workflow_runtime_api.py`

**Step 1: Write failing endpoint tests**

For requirements, tasks, and bugs, assign two items and assert the target handler, state-operation rows, and completed count all equal two. Add negative tests for duplicate or empty items, wrong type/project, mixed-project rows, non-member or disallowed-role targets, missing delegated reason, and stale transitions.

Add a rollback test: submit two items after invalidating the second transition, then assert neither item's owner/state or status-operation history changed.

**Step 2: Run it and verify it fails**

Run: `pytest backend/tests/test_workflow_runtime_api.py -k "batch_assignment" -v`

Expected: FAIL with missing route/service.

**Step 3: Add the controller route**

Add `POST /assignments/batch` before `/{object_type}/{object_id}/transition`; forward the typed request and current user to `execute_bulk_assignment`.

**Step 4: Refactor the runtime execution boundary**

Extract the single-item execution body after authentication into a private helper with a `commit` flag. The existing endpoint continues to call it with `commit=True` and retains its response. In batch mode, the helper creates status operations, audit data, and notifications in the session but does not commit.

**Step 5: Implement preflight and transaction**

`execute_bulk_assignment` must authenticate, reject unsupported type/empty/duplicate requests, reload each active item, check every item's type and project, resolve each transition against its current state, require `supported` metadata, validate the target with the existing manual-owner helper, and require a reason if any selected transition does. Execute every transition, call `db.commit()` once, and call `db.rollback()` before re-raising any exception.

**Step 6: Run it and verify it passes**

Run: `pytest backend/tests/test_workflow_runtime_api.py -k "batch_assignment" -v`

Expected: PASS, including rollback.

**Step 7: Commit**

Run: `git add backend/app/controllers/workflow_runtime_controller.py backend/app/services/workflow_runtime_service.py backend/app/views/workflow_runtime_view.py backend/tests/test_workflow_runtime_api.py`

Run: `git commit -m "feat: execute workflow assignments atomically in batch"`

### Task 4: Add frontend API and pure selection helpers

**Files:**

- Modify: `frontend/src/api/workflowRuntime.js`
- Create: `frontend/src/utils/batchAssignmentSelection.js`
- Create: `frontend/src/utils/batchAssignmentSelection.test.mjs`

**Step 1: Write failing helper tests**

Test transition extraction, first-selected project enforcement, candidate intersection, reason requirement, and selection reset when visible page IDs change:

```javascript
assert.deepEqual(eligibleAssigneeIds(selectedRows), [2, 5])
assert.equal(canSelectRow(otherProjectRow, selectedRows), false)
assert.equal(reasonRequired(selectedRows), true)
```

**Step 2: Run it and verify it fails**

Run: `npm --prefix frontend test -- batchAssignmentSelection`

Expected: FAIL because the helper does not exist.

**Step 3: Implement the smallest useful API and helper**

Add `executeWorkflowBulkAssignment(payload)` posting to `/workflow-runtime/assignments/batch`. Keep the utility pure: batch-capable transition lookup, same-project check, intersection of `eligible_assignee_ids`, reason calculation, and `{id, transition_id}` payload construction.

**Step 4: Run it and verify it passes**

Run: `npm --prefix frontend test -- batchAssignmentSelection`

Expected: PASS.

**Step 5: Commit**

Run: `git add frontend/src/api/workflowRuntime.js frontend/src/utils/batchAssignmentSelection.js frontend/src/utils/batchAssignmentSelection.test.mjs`

Run: `git commit -m "feat: add batch assignment frontend helpers"`

### Task 5: Build the shared bottom action control

**Files:**

- Create: `frontend/src/components/BatchAssignmentBar.vue`
- Create: `frontend/src/components/batchAssignmentBarBehavior.test.mjs`

**Step 1: Write failing component behavior tests**

Follow the existing source-based component test style. Assert a selected-count display, searchable `el-select`, metadata-driven required reason input, disabled/loading submit control, `append-to-body` confirmation dialog, and `completed`/`error` events.

**Step 2: Run it and verify it fails**

Run: `npm --prefix frontend test -- batchAssignmentBarBehavior`

Expected: FAIL because the component does not exist.

**Step 3: Implement the component**

Accept object type, selected rows with transitions, project members, and loading state. Derive candidates through `batchAssignmentSelection.js`; render a compact toolbar beside pagination; show an appended confirmation dialog; require a destination and any needed reason; call the new API; emit completion or the unmodified API error. Preserve selection on failure.

**Step 4: Run it and verify it passes**

Run: `npm --prefix frontend test -- batchAssignmentBarBehavior`

Expected: PASS.

**Step 5: Commit**

Run: `git add frontend/src/components/BatchAssignmentBar.vue frontend/src/components/batchAssignmentBarBehavior.test.mjs`

Run: `git commit -m "feat: add shared batch assignment toolbar"`

### Task 6: Integrate the three work-item lists

**Files:**

- Modify: `frontend/src/views/RequirementsView.vue`
- Modify: `frontend/src/views/TasksView.vue`
- Modify: `frontend/src/views/BugsView.vue`
- Create: `frontend/src/views/requirementsBatchAssignment.test.mjs`
- Create: `frontend/src/views/tasksBatchAssignment.test.mjs`
- Create: `frontend/src/views/bugsBatchAssignment.test.mjs`

**Step 1: Write failing integration tests**

For each target view, assert a selectable Element Plus selection column, `selection-change`, shared action bar placement beside pagination, same-project selectability, and selection reset during reload/page change. Add a static assertion that `frontend/src/views/TestsView.vue` imports neither the component nor a selection column.

**Step 2: Run it and verify it fails**

Run: `npm --prefix frontend test -- requirementsBatchAssignment tasksBatchAssignment bugsBatchAssignment`

Expected: FAIL because the lists are not integrated.

**Step 3: Implement view integration**

Each view gets a table ref and selected-row ref. Use `workflowTransitionsFor(row)` and the pure helper in the `selectable` predicate; discard rows outside the first selected project; pass `membersForProject(selectedProjectId)` to the bar; clear Element Plus selection before data replacement, when the page changes, and after success; reload on completion. Do not alter fixed operation columns or any test-case list behavior.

**Step 4: Run it and verify it passes**

Run: `npm --prefix frontend test -- requirementsBatchAssignment tasksBatchAssignment bugsBatchAssignment`

Expected: PASS.

**Step 5: Commit**

Run: `git add frontend/src/views/RequirementsView.vue frontend/src/views/TasksView.vue frontend/src/views/BugsView.vue frontend/src/views/requirementsBatchAssignment.test.mjs frontend/src/views/tasksBatchAssignment.test.mjs frontend/src/views/bugsBatchAssignment.test.mjs`

Run: `git commit -m "feat: batch assign work items from lists"`

### Task 7: Verify regression and layout

**Files:**

- Modify only if verification identifies a defect.

**Step 1: Run backend tests**

Run: `pytest backend/tests/test_workflow_runtime_api.py -v`

Expected: PASS.

**Step 2: Run all frontend tests**

Run: `npm --prefix frontend test`

Expected: PASS.

**Step 3: Build the frontend**

Run: `npm --prefix frontend run build`

Expected: Vite build completes without errors.

**Step 4: Validate the diff**

Run: `git diff --check`

Expected: no output and exit code 0.

**Step 5: Browser verification**

At desktop and narrow widths, select two same-project rows in each list; confirm candidate filtering, reason validation, completion refresh, and selection reset after paging. Confirm Tests remains without a batch action area and that pagination never overlaps the bottom toolbar.

**Step 6: Commit any verification-only fix**

Run: `git add <only files changed by verification fixes>`

Run: `git commit -m "fix: polish batch assignment list behavior"`
