# Workbench Scalability Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the workbench usable when iterations and work items grow by adding personal/global views, stronger filters, collapsible boards, lane-level scrolling, and progressive card display.

**Architecture:** Keep the existing backend workbench API and drag move API unchanged. Implement the scalability layer in `DashboardView.vue` with client-side state for view mode, filters, expansion, and per-lane display limits, then adjust CSS so work item overflow is contained inside each lane.

**Tech Stack:** Vue 3 Composition API, Element Plus, vue-draggable-plus, existing Axios API wrappers.

---

### Task 1: Add Workbench View State And Filters

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`

**Step 1: Add state**

Add:
- `viewMode = ref('mine')`
- `iterationFilter = ref([])`
- `keywordFilter = ref('')`
- `currentUser = ref(null)`

Read the current user from local storage using existing auth storage keys if present. Match by `id`, `user_id`, or `full_name` conservatively.

**Step 2: Update filtering**

Change `filterItems` so:
- `mine` view keeps only current user's owned items when a current user is known.
- owner filter still works in both modes.
- keyword filter matches title and project name.
- iteration filter limits visible boards.

**Step 3: Verify**

Run:
`npm run build`

Expected: build succeeds.

**Step 4: Commit**

```bash
git add frontend/src/views/DashboardView.vue
git commit -m "feat: add workbench view filters"
```

### Task 2: Add Collapsible Boards And Progressive Lane Display

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`

**Step 1: Add state**

Add:
- `expandedIterationIds = ref(new Set())`
- `laneLimits = reactive({})`
- constant `INITIAL_LANE_LIMIT = 8`
- constant `LANE_LIMIT_STEP = 8`

Initialize expanded boards after loading workbench: expand the first visible iteration.

**Step 2: Update template**

Add expand/collapse control to each iteration header. Render lanes only when the iteration is expanded. In each lane, render only `visibleLaneItems(iteration.id, group.key, group.items)`. Add a "显示更多" button when there are hidden items.

**Step 3: Preserve drag behavior**

Ensure drag still receives the full item id and type. `group.items` remains the source array, but template only renders the visible slice.

**Step 4: Verify**

Run:
`npm run build`

Expected: build succeeds.

**Step 5: Commit**

```bash
git add frontend/src/views/DashboardView.vue
git commit -m "feat: make workbench boards collapsible"
```

### Task 3: Contain Workbench Overflow In CSS

**Files:**
- Modify: `frontend/src/styles.css`

**Step 1: Update layout CSS**

Adjust:
- `.workbench-board` to use a responsive grid.
- `.iteration-board` to avoid expanding beyond viewport width.
- `.workbench-lanes` to use responsive columns.
- `.workbench-card-list` to set `max-height` and `overflow-y: auto`.
- Card and action styles to stay compact and avoid wrapping the operation area into unusable rows.

**Step 2: Verify**

Run:
`npm run build`

Expected: build succeeds.

**Step 3: Commit**

```bash
git add frontend/src/styles.css
git commit -m "style: contain workbench board overflow"
```

### Task 4: Final Verification And Sub-Agent Review

**Files:**
- No direct edits expected.

**Step 1: Run verification**

Run:
- `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests -q`
- `npm run build` in `frontend`
- `git diff --check`

Expected:
- Backend tests pass.
- Frontend build succeeds.
- Diff check has no errors except possible Windows line ending warnings.

**Step 2: Dispatch sub-agent verification**

Ask a sub-agent to review the workbench against the design goals and score it out of 100. Passing threshold: greater than 90.

**Step 3: Fix gaps if score is 90 or lower**

If score is 90 or lower, implement the highest-impact gaps, verify, commit, and ask for another sub-agent review.

**Step 4: Push**

```bash
git push origin main
```
