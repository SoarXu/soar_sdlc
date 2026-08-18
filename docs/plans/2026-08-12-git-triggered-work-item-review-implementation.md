# Git-Triggered Work Item Review Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a development-lead review gate for requirements, tasks, and bugs, automatically triggered by linked Git commits.

**Architecture:** Extend default workflow templates with review transitions, persist a single active review round per work item, and invoke it from the existing commit ingestion service. Workflow transitions remain the authority for status mutation; the review round is the authority for reviewer assignment, decisions, and workbench visibility.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, pytest, Vue 3, Element Plus.

---

### Task 1: Add Work Item Review-Round Persistence

**Files:**
- Modify: `backend/app/models/devops.py`
- Create: `backend/alembic/versions/20260812_001_git_triggered_work_item_reviews.py`
- Modify: `backend/tests/conftest.py`
- Test: `backend/tests/test_work_item_review_migration.py`

**Step 1:** Write a failing test asserting one active review round per object, latest commit linkage, reviewer, decision, and remark fields.

**Step 2:** Run `pytest tests/test_work_item_review_migration.py -v`; expect failure.

**Step 3:** Add the model and idempotent migration with indexes for reviewer/status and object/status.

**Step 4:** Re-run the test; expect pass.

### Task 2: Install Review Subgraphs in Default Workflows

**Files:**
- Modify: `backend/app/services/workflow_state_service.py`
- Create: `backend/alembic/versions/20260812_002_default_workflow_review_subgraphs.py`
- Test: `backend/tests/test_default_workflow_review_subgraphs.py`

**Step 1:** Write failing tests for Requirement, Task, Bug templates: states include `待评审`, `submit_review` targets it, `approve_review` proceeds, and `reject_review` returns to development with `development_lead` only.

**Step 2:** Run the focused test; expect failure.

**Step 3:** Add idempotent review states/transitions without overwriting custom workflow graphs.

**Step 4:** Re-run the test; expect pass.

### Task 3: Trigger and Maintain Review Rounds from Commit Ingestion

**Files:**
- Create: `backend/app/services/work_item_review_service.py`
- Modify: `backend/app/services/devops_service.py`
- Test: `backend/tests/test_git_triggered_work_item_review.py`

**Step 1:** Write failing tests for one `REQ/TASK/BUG` commit, multi-item commit, repeated commit idempotency, and new commits while waiting review updating the open round.

**Step 2:** Run focused tests; expect failure.

**Step 3:** Call the review service after successful commit link resolution. It must transition only through the configured workflow transition and create/reuse the active review round assigned to development lead.

**Step 4:** Re-run focused tests; expect pass.

### Task 4: Add Review Decision and Workbench APIs

**Files:**
- Modify: `backend/app/controllers/devops_controller.py`
- Modify: `backend/app/views/devops_view.py`
- Modify: `backend/app/services/dashboard_service.py`
- Modify: `backend/app/views/dashboard_view.py`
- Test: `backend/tests/test_work_item_review_api.py`
- Test: `backend/tests/test_dashboard_work_item_reviews.py`

**Step 1:** Write failing tests for approve/reject permissions, state transitions, decision audit, and current development-lead workbench listing.

**Step 2:** Run focused tests; expect failure.

**Step 3:** Implement approval/rejection endpoints and expose active review rounds in the workbench response.

**Step 4:** Re-run focused tests; expect pass.

### Task 5: Add Workbench and DevOps Review UI

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/views/DevopsView.vue`
- Modify: `frontend/src/api/dashboard.js`
- Modify: `frontend/src/api/devops.js`
- Test: `frontend/src/views/gitTriggeredReviewWorkbench.test.mjs`

**Step 1:** Write failing source tests for the `待我评审` section, latest commit Diff navigation, and approve/reject actions.

**Step 2:** Run the focused frontend test; expect failure.

**Step 3:** Implement concise review actions, reason capture for rejection, and refresh state after decisions.

**Step 4:** Run focused backend/frontend suites and manually verify `REQ-1505` end-to-end.
