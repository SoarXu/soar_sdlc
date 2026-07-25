# Workflow Manual Assignee Scope Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Restrict every manually selected next-handler dropdown to active members of the work item's project, with optional project-role filtering.

**Architecture:** The workflow runtime service will expose action-level `eligible_assignee_ids` computed from project membership and `manual_owner_roles`. The single-action UI will filter its user options by this server-provided contract, while bulk assignment will reuse the same backend candidate resolver.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Element Plus, Node source-contract tests, pytest

---

### Task 1: Add the action-level candidate contract

**Files:**
- Modify: `backend/app/views/workflow_runtime_view.py`
- Modify: `backend/app/services/workflow_runtime_service.py`
- Test: `backend/tests/test_workflow_runtime_api.py`

**Step 1: Write the failing backend tests**

Add assertions that a manual-owner transition returns `eligible_assignee_ids` containing only active members of the work item's project, and that `manual_owner_roles` narrows the result.

**Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_workflow_runtime_api.py -q`

Expected: FAIL because `WorkflowTransitionActionRead` has no action-level `eligible_assignee_ids`.

**Step 3: Implement the shared candidate resolver**

Add `eligible_assignee_ids: list[int]` to the action response. Extract a helper that joins `ProjectMember` to active, non-deleted `User` rows, filters by `project_id`, and optionally filters `ProjectMember.project_role` by `manual_owner_roles`. Use it for both action metadata and bulk-assignment metadata.

**Step 4: Run backend tests**

Run: `pytest backend/tests/test_workflow_runtime_api.py -q`

Expected: all workflow runtime API tests pass.

### Task 2: Filter the single-action dropdown

**Files:**
- Modify: `frontend/src/components/WorkflowActionButtons.vue`
- Test: `frontend/src/components/workflowActionButtonsBehavior.test.mjs`

**Step 1: Write the failing frontend test**

Assert that the next-handler options iterate an action-filtered candidate list instead of the unfiltered global `users` list.

**Step 2: Run the test to verify it fails**

Run: `npm test -- workflowActionButtonsBehavior`

Expected: FAIL because the template currently uses `v-for="user in users"`.

**Step 3: Implement candidate filtering**

Add a computed candidate list that intersects the loaded active users with `activeAction.eligible_assignee_ids`. Keep the list empty when the server returns no eligible IDs; do not fall back to all users.

**Step 4: Run the frontend test**

Run: `npm test -- workflowActionButtonsBehavior`

Expected: the workflow action button behavior test passes.

### Task 3: Full verification

**Files:**
- Verify only

**Step 1: Run backend workflow tests**

Run: `pytest backend/tests/test_workflow_runtime_api.py -q`

**Step 2: Run all frontend tests**

Run: `npm test` from `frontend/`.

**Step 3: Build the frontend**

Run: `npm run build` from `frontend/`.

**Step 4: Check whitespace and served source**

Run `git diff --check` for touched files and verify the Vite development server serves the filtered dropdown implementation.
