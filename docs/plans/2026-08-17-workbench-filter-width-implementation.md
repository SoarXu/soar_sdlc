# Workbench Filter Width Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make every desktop workbench toolbar filter match the title search input width.

**Architecture:** The `DashboardView.vue` template already assigns a shared `workbench-filter` class to each select. The stylesheet is the sole source of the width mismatch, so one shared CSS rule change corrects every select while retaining the existing responsive media query.

**Tech Stack:** Vue 3, Element Plus, Vite, Node.js source-level tests.

---

### Task 1: Add the toolbar width regression test

**Files:**
- Modify: `frontend/src/utils/workbenchViewModel.test.mjs`
- Verify: `frontend/src/utils/workbenchViewModel.test.mjs`

**Step 1: Write the failing test**

Add a test that reads `frontend/src/styles.css` and asserts both `.workbench-filter` and `.workbench-search` use `width: 260px` in their desktop declarations.

**Step 2: Run test to verify it fails**

Run: `npm test -- workbenchViewModel`

Expected: FAIL because `.workbench-filter` is currently 150px wide.

### Task 2: Align the shared desktop filter width

**Files:**
- Modify: `frontend/src/styles.css:1097`
- Test: `frontend/src/utils/workbenchViewModel.test.mjs`

**Step 1: Write minimal implementation**

Change `.workbench-filter` to:

```css
.workbench-filter {
  flex: 0 0 260px;
  min-width: 160px;
  max-width: 260px;
  width: 260px;
}
```

**Step 2: Run the focused regression test**

Run: `npm test -- workbenchViewModel`

Expected: PASS.

**Step 3: Run the frontend build**

Run: `npm run build`

Expected: Vite build completes with exit code 0.

**Step 4: Visually verify**

Open the workbench at desktop width and confirm all eight toolbar controls are 260px wide; shrink the viewport to confirm the existing responsive behavior still wraps controls without fixed-width overflow.

**Step 5: Commit**

Do not commit without the user's explicit delivery confirmation. If approved, stage only the style, test, and plan files, then create the requested commit.
