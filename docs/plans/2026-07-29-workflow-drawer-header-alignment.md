# Workflow Drawer Header Alignment Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align the selected transition context with the upper-left of the advanced workflow configuration drawer.

**Architecture:** Keep Element Plus' drawer close action in its default upper-right location. Group the optional back button with the title and state-route summary in a left-aligned header region. No data flow or drawer behavior changes.

**Tech Stack:** Vue 3 Composition API, Element Plus, Node.js source-contract tests.

---

### Task 1: Cover And Align The Drawer Header

**Files:**
- Modify: `frontend/src/components/workflowAdvancedConfigDrawer.test.mjs`
- Modify: `frontend/src/components/WorkflowAdvancedConfigDrawer.vue:12-22,665-671`

**Step 1: Write the failing test**

Require a `drawer-header__leading` wrapper around the back action and context title, and require a left-aligned header layout.

**Step 2: Run test to verify it fails**

Run: `npm test -- workflowAdvancedConfigDrawer`

Expected: FAIL because the leading header group does not exist.

**Step 3: Write minimal implementation**

Wrap the existing back button and title in `drawer-header__leading`. Change the header layout from distributed alignment to left alignment while retaining right padding for Element Plus' close button.

**Step 4: Run test to verify it passes**

Run: `npm test -- workflowAdvancedConfigDrawer`

Expected: PASS.

**Step 5: Run regression verification**

Run: `npm test`

Expected: PASS with all frontend source-contract tests.
