# Workbench Density Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the card-heavy default workbench with a dense list-first experience, keep the board for drag scheduling, and add a statistics view plus a detail action drawer.

**Architecture:** Keep backend APIs unchanged. Flatten the existing filtered iteration data into table rows for the default list view, reuse existing lifecycle methods from `DashboardView.vue`, and restyle board cards into compact schedule rows. Use Element Plus table, pagination, tabs, drawer, and descriptions.

**Tech Stack:** Vue 3 Composition API, Element Plus, vue-draggable-plus, existing Axios API wrappers.

---

### Task 1: Add View Tabs And Dense List View

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/styles.css`

**Steps:**
1. Add `displayMode = ref('list')`, `listPage`, and `listPageSize`.
2. Add computed `flatWorkbenchItems` and `pagedWorkbenchItems` from `filteredIterations`.
3. Add an Element Plus tab/radio switch for `列表 / 看板 / 统计`.
4. Render an Element Plus table for list mode with type, title, project, iteration, owner, status, priority/result, and operation entry.
5. Add pagination under the table.
6. Build and commit.

### Task 2: Add Detail Drawer Actions

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`

**Steps:**
1. Add `selectedWorkItem` and drawer visibility state.
2. Add `openWorkItemDrawer(item, iteration)` helper.
3. Move lifecycle buttons into a reusable template block rendered in the drawer.
4. Keep a detail-page button in the drawer.
5. Change list title and board mini row click to open drawer.
6. Build and commit.

### Task 3: Compact Board And Statistics View

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`
- Modify: `frontend/src/styles.css`

**Steps:**
1. Show existing draggable board only when `displayMode === 'board'`.
2. Convert board cards to compact rows.
3. Add statistics mode with iteration-level counts and totals.
4. Keep board drag, rollback, and show-more behavior.
5. Build and commit.

### Task 4: Final Verification And Review

**Files:**
- No direct edits expected.

**Steps:**
1. Run backend tests: `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests -q`.
2. Run frontend build: `npm run build` in `frontend`.
3. Run `git diff --check`.
4. Ask a sub-agent to score the implementation. Passing threshold: greater than 90.
5. If score is 90 or lower, fix gaps, commit, and re-review.
6. Push to `origin main`.
