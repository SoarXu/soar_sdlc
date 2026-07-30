# Mentioned Comments Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Show each comment that mentions the current user as an individual row in the workbench's “提到我的” list.

**Architecture:** Enrich the existing `WorkbenchItem` response model with comment fields. Build mention rows directly from `WorkItemComment` records while reusing the established work-item loader for permission-independent work-item metadata and the existing active/project scope filter. Render comment-specific columns only for the `mentioned_me` tab.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Element Plus, Node test runner, pytest.

---

### Task 1: Lock the API response behavior

**Files:**
- Modify: `backend/tests/test_dashboard_workbench_api.py`
- Modify: `backend/app/views/dashboard_view.py`
- Modify: `backend/app/services/dashboard_service.py`

**Step 1: Write the failing test**

Add a test that creates two comments mentioning the same user on one active bug. Assert that `mentioned_me` contains two rows, each with its distinct comment ID, body, author ID, and comment timestamp, ordered newest first.

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_dashboard_workbench_api.py -k mentioned_comment -v`

Expected: FAIL because the response only deduplicates work-item references and lacks comment fields.

**Step 3: Write minimal implementation**

Add nullable comment fields to `WorkbenchItem`. Include `mentioned_comment_id`, `mentioned_comment_body`, `mentioned_comment_author_id`, and `mentioned_comment_create_time` in mention refs. Add a loader mode that preserves individual refs for the mentioned section, then apply existing scope filtering and comment-time descending ordering.

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_dashboard_workbench_api.py -k mentioned_comment -v`

Expected: PASS.

### Task 2: Render the comment-centric tab

**Files:**
- Modify: `frontend/src/utils/workbenchViewModel.test.mjs`
- Modify: `frontend/src/utils/workbenchViewModel.js`
- Modify: `frontend/src/views/DashboardView.vue`

**Step 1: Write the failing test**

Assert the tab description says the list displays mention comments and assert the dashboard template contains the comment-specific columns guarded by `activeListSection.key === 'mentioned_me'`.

**Step 2: Run test to verify it fails**

Run: `npm test -- workbenchViewModel`

Expected: FAIL because the description and columns do not exist.

**Step 3: Write minimal implementation**

Update the description. Hide standard work-item columns that distract from comment context in this tab and add “评论内容”, “评论人”, and “评论时间” columns, using the existing user name resolver and date formatter. Preserve the linked work-item title.

**Step 4: Run test to verify it passes**

Run: `npm test -- workbenchViewModel`

Expected: PASS.

### Task 3: Verify the integrated change

**Files:**
- Verify: `backend/tests/test_dashboard_workbench_api.py`
- Verify: `frontend/src/utils/workbenchViewModel.test.mjs`
- Verify: `frontend/src/views/DashboardView.vue`

**Step 1: Run focused automated checks**

Run: `pytest backend/tests/test_dashboard_workbench_api.py -v`

Run: `npm test`

Run: `npm run build`

**Step 2: Review the final diff**

Run: `git diff --check HEAD^..HEAD` and `git status --short`.
