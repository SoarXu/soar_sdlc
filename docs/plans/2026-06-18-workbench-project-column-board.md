# Workbench Project Column Board Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reorganize the workbench board so single-project iterations stay under their project column, while multi-project iterations are shown in a shared iteration area.

**Architecture:** Keep the existing workbench API and move endpoint unchanged. Reuse the `iteration.projects` data already returned by the backend, group filtered iterations on the frontend into shared iterations and project columns, and render the existing iteration board card in those groups.

**Tech Stack:** Vue 3 Composition API, Element Plus, vue-draggable-plus, existing dashboard API.

---

## Layout Rules

1. Iterations with exactly one related project are placed in that project's column.
2. Iterations with zero or more than one related project are placed in a shared iteration section.
3. Project columns are sorted by project name.
4. Iterations inside each column are sorted by start date, then id.
5. Drag target is still an iteration lane, not the project column itself.
6. Backend `move_workbench_item` remains the source of truth for project-scope validation.

## Tasks

### Task 1: Add Frontend Grouping

Modify `frontend/src/views/DashboardView.vue`:

- Add computed `sharedBoardIterations`.
- Add computed `projectBoardColumns`.
- Add helper `sortIterationsForBoard`.
- Preserve `filteredIterations`, `visibleGroups`, drag handlers, collapse state, and drawer behavior.

### Task 2: Render Shared Area And Project Columns

Modify `frontend/src/views/DashboardView.vue`:

- Replace the board's flat `v-for="iteration in filteredIterations"` with:
  - shared iteration section when shared iterations exist
  - project column section for single-project iterations
- Keep existing iteration card internals.

### Task 3: Add Board Column Styles

Modify `frontend/src/styles.css`:

- Add styles for shared section, project column shell, project column headers, and cards inside columns.
- Keep compact card and lane styles.

### Task 4: Verification

Run:

- `npm run build` in `frontend`
- `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests -q`
- `git diff --check`

Then commit and push.
