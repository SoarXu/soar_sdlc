# Workflow Node Drag Click Suppression Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent a workflow node drag from opening the state configuration drawer when the mouse is released.

**Architecture:** Track whether pointer movement exceeds a 4px drag threshold. When a moved drag ends, suppress only the immediately following click for that node and clear the suppression automatically if no click is dispatched.

**Tech Stack:** Vue 3 Composition API, JavaScript source-contract tests, Node.js assert, Vite

---

### Task 1: Add Drag Click Suppression

**Files:**
- Modify: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`
- Modify: `frontend/src/components/WorkflowDesigner.vue`

**Step 1: Write the failing test**

Require the node template to call `handleStateClick(state)`. Require `startDrag` to reset a movement flag, `onDrag` to set it only after the squared pointer distance exceeds `16`, and `stopDrag` to remember the dragged node ID only when movement occurred. Require `handleStateClick` to consume the matching suppression marker without calling `selectState`, while normal clicks call `selectState(state)`.

**Step 2: Run the focused test to verify RED**

Run: `cd frontend; npm test -- workflowDesignerAutoLayout`

Expected: FAIL because `handleStateClick` and the suppression state do not exist.

**Step 3: Implement the minimal behavior**

Add `moved` to the drag state and a short-lived `suppressedStateClickId` ref. Use a 4px threshold in `onDrag`. Capture the dragged node before clearing state in `stopDrag`, set suppression only for a moved drag, and clear it with `setTimeout(..., 0)`. Route node clicks through `handleStateClick`.

**Step 4: Run focused tests to verify GREEN**

Run: `cd frontend; npm test -- workflowDesignerAutoLayout workflowViewport workflowDragViews`

Expected: all selected tests pass.

**Step 5: Run full frontend verification**

Run: `cd frontend; npm test; npm run build`

Expected: all tests pass and Vite exits with code 0.

**Step 6: Commit**

```powershell
git add docs/plans/2026-07-21-workflow-node-drag-click-suppression-design.md docs/plans/2026-07-21-workflow-node-drag-click-suppression.md frontend/src/components/workflowDesignerAutoLayout.test.mjs frontend/src/components/WorkflowDesigner.vue
git commit -m "fix: keep workflow drawer closed after node drag"
```
