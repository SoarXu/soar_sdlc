# 项目迭代操作列动态宽度 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Size the project iteration action column from its runtime and local actions so no visible action is clipped.

**Architecture:** `ProjectDetailView` will reuse the existing `workflowActionColumnWidth` utility. The computed width considers runtime iteration transitions plus an allowance for deferring work items, editing, and deleting.

**Tech Stack:** Vue 3, Element Plus, Node assert tests, Vite.

---

### Task 1: Capture the fixed-width regression

**Files:**
- Modify: `frontend/src/views/projectDetailWorkflowIterationLayout.test.mjs`

**Step 1: Write the failing test**

Assert that the iteration table binds its operation column to `projectIterationOperationWidth`, and that the view defines this value with `workflowActionColumnWidth`.

**Step 2: Run the test to verify it fails**

Run: `npm test -- projectDetailWorkflowIterationLayout`

Expected: FAIL because the column uses `width="250"`.

### Task 2: Calculate the operation width

**Files:**
- Modify: `frontend/src/views/ProjectDetailView.vue`

**Step 1: Import the existing utility**

Add `workflowActionColumnWidth` from `../utils/workflowActionColumn`.

**Step 2: Define the computed width**

Calculate `projectIterationOperationWidth` from the current iteration rows and their loaded runtime transitions, with `minWidth: 320` and `extraWidth: 184` for the three local actions.

**Step 3: Bind the column**

Replace the fixed iteration operation-column width with `:width="projectIterationOperationWidth"`.

**Step 4: Run the focused test**

Run: `npm test -- projectDetailWorkflowIterationLayout`

Expected: PASS.

### Task 3: Verify frontend behavior

**Files:**
- Verify: `frontend/src/views/projectDetailWorkflowIterationLayout.test.mjs`
- Verify: `frontend/package.json`

**Step 1: Run all frontend tests**

Run: `npm test`

Expected: PASS.

**Step 2: Build production assets**

Run: `npm run build`

Expected: exits with code 0.
