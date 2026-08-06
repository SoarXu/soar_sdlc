# 组件事项手动指派候选范围 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Ensure manual-assignment candidates for a work item bound to a primary business component are limited to that component's active members.

**Architecture:** Keep component transition routes as the first candidate-resolution path. When no component route exists, obtain the primary component's active members and apply the existing manual-owner role configuration to their `component_role`; only items without a primary component continue to query project members.

**Tech Stack:** FastAPI, SQLAlchemy, pytest, React/Vite verification.

---

### Task 1: Capture the regression

**Files:**
- Modify: `backend/tests/test_business_components_api.py`

**Step 1: Write the failing test**

Create a component from a closed source project with two `developer` members, then update the component team to retain only one. Create a requirement bound to the component and assert manual-assignment candidates include the retained component user and exclude the removed source-project member.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_business_components_api.py -k component_bound_manual_assignment -v`

Expected: FAIL because the generic project-member candidate query contains both users.

### Task 2: Restrict component-bound candidates

**Files:**
- Modify: `backend/app/services/business_component_service.py`
- Modify: `backend/app/services/workflow_runtime_service.py`

**Step 1: Add component-member lookup**

Add a small service helper that returns enabled members for an item's primary component, or `None` when no primary component is bound.

**Step 2: Apply the existing manual-role rule inside the component boundary**

In `_eligible_transition_assignee_ids`, preserve the component-route branch. When it does not apply and the helper returns component members, return only member user IDs whose `component_role` matches `_manual_owner_roles(rule)`; return all enabled component members for no roles or `project_member`. Do not call the project-member resolver in this branch.

**Step 3: Run regression test**

Run: `pytest tests/test_business_components_api.py -k component_bound_manual_assignment -v`

Expected: PASS.

### Task 3: Verify affected surfaces

**Files:**
- Verify: `backend/tests/test_business_components_api.py`
- Verify: `frontend/package.json`

**Step 1: Run component API tests**

Run: `pytest tests/test_business_components_api.py -v`

Expected: PASS.

**Step 2: Build frontend**

Run: `npm run build` from `frontend`.

Expected: build completes with exit code 0.

**Step 3: Review the diff**

Run: `git diff -- backend/app/services/business_component_service.py backend/app/services/workflow_runtime_service.py backend/tests/test_business_components_api.py docs/plans/2026-08-06-component-assignment-candidates-design.md docs/plans/2026-08-06-component-assignment-candidates-implementation-plan.md`

Expected: only the documented candidate-scope behavior, regression test, and plans are changed.
