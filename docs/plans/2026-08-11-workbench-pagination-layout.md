# 工作台分页与满屏布局 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fill the remaining workbench viewport with the list panel and paginate filtered, sorted work items on the client.

**Architecture:** Keep the existing backend payload unchanged. Add a small pure pagination helper beside the workbench filter/sort helpers, then bind page state and Element Plus pagination in `DashboardView.vue`; CSS flex tracks keep the table panel and footer stable across viewport heights.

**Tech Stack:** Vue 3 Composition API, Element Plus, Node built-in assertions, Vite.

---

### Task 1: Define pagination behavior with failing tests

**Files:**
- Modify: `frontend/src/utils/workbenchViewModel.test.mjs`
- Modify: `frontend/src/utils/workbenchViewModel.js`

**Step 1: Write failing helper tests**

Add assertions for a pure `paginateWorkbenchItems(items, page, pageSize)` helper: page 1 returns the first slice, later pages return the correct slice, invalid pages clamp to a valid page, and the returned metadata includes the corrected page and total.

**Step 2: Run the focused test and verify RED**

Run: `npm test workbenchViewModel`

Expected: FAIL because the pagination helper is not exported.

**Step 3: Implement the minimal helper**

Export the helper without mutating the input array. Normalize page size to a positive integer, calculate at least one logical page for an empty list, clamp the requested page, and return `{ items, page, pageSize, total, pageCount }`.

**Step 4: Run the focused test and verify GREEN**

Run: `npm test workbenchViewModel`

Expected: PASS.

### Task 2: Bind pagination and full-height layout

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/styles.css`
- Modify: `frontend/src/utils/workbenchViewModel.test.mjs`

**Step 1: Add failing source-contract assertions**

Assert that the table consumes `pagedListItems`, an `el-pagination` binds current page/page size with `[10, 20, 50, 100]`, and the workbench layout uses flex/grid tracks that keep the list section and table body at `min-height: 0` while the pagination footer stays outside the scrollable table area.

**Step 2: Run the focused test and verify RED**

Run: `npm test workbenchViewModel`

Expected: FAIL because the view has no page state, paged data or pagination footer.

**Step 3: Implement the view behavior**

Add `currentPage` and `pageSize` refs with default 1 and 20. Compute pagination from the filtered/sorted list, bind the table to the paged items, clear selection before page changes, reset page to 1 when any filter changes, and correct the current page when the result count shrinks. Add an Element Plus pagination footer with total, sizes, previous/next and jumper controls.

**Step 4: Implement the layout**

Make `.workbench-page`, `.workbench-list`, `.workbench-list-section`, and `.workbench-list-table` fill their available height. Keep the pagination footer at the bottom and let the table flex within the remaining area without the existing fixed internal max-height behavior.

**Step 5: Run frontend verification**

Run: `npm test`

Expected: PASS.

Run: `npm run build`

Expected: Vite build completes successfully.

### Task 3: Git handling

Do not stage, commit, push, create a pull request, or merge until the user selects a delivery option after implementation and verification.
