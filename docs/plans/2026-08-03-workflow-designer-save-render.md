# Workflow Designer Save and Render Implementation Plan

> **For Codex:** REQUIRED SKILL: Use `executing-plans` to implement this plan task-by-task.

**Goal:** Prevent false unsaved-change prompts after a successful workflow graph save and render valid straight transitions immediately when stored generated routes have no waypoints.

**Architecture:** Keep the advanced configuration draft authoritative until it is explicitly applied or discarded. Reset its draft after either an explicit discard or a graph save response. Make the stored-route decoder return a direct two-point segment when the anchored endpoints are already horizontally or vertically aligned.

**Tech Stack:** Vue 3 Composition API, Element Plus, Node built-in assertions.

---

### Task 1: Cover direct generated routes

**Files:**
- Modify: `frontend/src/utils/workflowManualRoute.test.mjs`
- Modify: `frontend/src/utils/workflowManualRoute.js`

**Step 1: Write the failing test**

Add a generated route with valid right/left anchors, an empty `waypoints` array, and aligned source and target nodes. Assert that `diagramRoutePoints` returns the two anchored endpoints.

**Step 2: Run test to verify it fails**

Run: `npm run test -- workflowManualRoute`

Expected: failure from attempting to modify an empty waypoint list.

**Step 3: Write minimal implementation**

Return `[start, end]` before mutating waypoint endpoints when an aligned route has no intermediate waypoints.

**Step 4: Run test to verify it passes**

Run: `npm run test -- workflowManualRoute workflowEdgePath`

Expected: both tests pass.

### Task 2: Keep advanced drafts accurate across discard and save

**Files:**
- Modify: `frontend/src/components/WorkflowAdvancedConfigDrawer.vue`
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Modify: `frontend/src/views/workflowViewUnsavedGuard.test.mjs`

**Step 1: Write failing source-contract regressions**

Assert that an explicit discard resets the advanced draft and that a successful graph response refreshes the drawer draft before capturing the saved graph snapshot.

**Step 2: Run tests to verify they fail**

Run: `npm run test -- workflowViewUnsavedGuard workflowAdvancedConfigDrawer`

Expected: the new assertions fail against the current stale-draft behavior.

**Step 3: Write minimal implementation**

Expose a draft refresh method on the drawer. Invoke it after an explicit discard and after the parent replaces graph data following a successful save. Do not refresh it on validation or HTTP failure.

**Step 4: Run tests to verify they pass**

Run: `npm run test -- workflowViewUnsavedGuard workflowAdvancedConfigDrawer workflowDesignerAutoLayout`

Expected: all selected tests pass.

### Task 3: Verify integration

**Files:**
- No production files expected beyond Tasks 1-2.

**Step 1: Run workflow-focused suite**

Run: `npm run test -- workflow`

Expected: all workflow tests pass.

**Step 2: Build the frontend**

Run: `npm run build`

Expected: Vite completes successfully.

**Step 3: Inspect changes**

Run: `git diff --check` and `git status --short`.

Expected: only the planned source, test, and plan files are modified.

**Delivery:** Do not commit, push, create a pull request, or merge without the user's explicit delivery choice.
