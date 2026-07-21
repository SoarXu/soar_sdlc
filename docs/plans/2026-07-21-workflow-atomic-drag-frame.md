# Workflow Atomic Drag Frame Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Render workflow nodes and their fully routed connections from one atomic coordinate snapshot during dragging.

**Architecture:** Add a focused drag-frame utility that clones only the moved node, runs the existing full edge router, and returns `{ states, transitionViews }` as one immutable frame. The Vue component publishes that frame only after routing finishes, renders both nodes and edges from it, and commits the final node coordinates on mouseup.

**Tech Stack:** Vue 3 Composition API, JavaScript ES modules, Node.js assert tests, existing workflow edge router, Vite

---

### Task 1: Build The Atomic Drag Frame

**Files:**
- Create: `frontend/src/utils/workflowDragFrame.js`
- Create: `frontend/src/utils/workflowDragFrame.test.mjs`

**Step 1: Write the failing test**

Create automatic incoming/outgoing edges and a manual edge for one dragged node. Call the proposed API:

```js
const frame = createWorkflowDragFrame(
  states,
  transitions,
  'dragged',
  { x: 640, y: 360 },
  (transition) => transition.id
)
```

Assert that the frame contains the moved node at the requested coordinates, every associated edge endpoint lies on that moved node's border, and the original `states` and `transitions` remain unchanged.

**Step 2: Run the focused test to verify RED**

Run: `cd frontend; npm test -- workflowDragFrame`

Expected: FAIL because `workflowDragFrame.js` does not exist.

**Step 3: Implement the minimal frame builder**

Export `createWorkflowDragFrame(states, transitions, stateId, position, transitionKey)`. Return `null` for invalid input. Create a new states array whose dragged entry is `{ ...state, x, y }`, then return:

```js
{
  states: previewStates,
  transitionViews: buildWorkflowEdgeViews(previewStates, transitions, transitionKey)
}
```

**Step 4: Run the focused test to verify GREEN**

Run: `cd frontend; npm test -- workflowDragFrame workflowEdgePath workflowManualRoute`

Expected: all selected tests pass.

### Task 2: Publish And Commit One Drag Frame

**Files:**
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Modify: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`
- Modify: `frontend/scripts/run-tests.mjs`

**Step 1: Write the failing component contract**

Require the component to import `createWorkflowDragFrame`, render nodes from `renderedStates`, and select both rendered states and transition views from one `dragFrame` ref. Require `flushNodeDrag` to assign a complete frame and forbid direct `dragging.state.x/y` mutation. Require `stopDrag` to commit final coordinates from the frame before clearing it.

**Step 2: Run the focused test to verify RED**

Run: `cd frontend; npm test -- workflowDesignerAutoLayout workflowDragFrame`

Expected: FAIL because the component still mutates the business node directly.

**Step 3: Implement atomic frame publication**

Add `dragFrame = ref(null)` and:

```js
const renderedStates = computed(() => dragFrame.value?.states || states.value)
const transitionViews = computed(() => dragFrame.value?.transitionViews || fullTransitionViews.value)
```

Use `renderedStates` for node rendering and canvas bounds. In `flushNodeDrag`, compute the clamped target coordinate and assign one result from `createWorkflowDragFrame`. In `stopDrag`, flush the pending pointer, copy the dragged node coordinates from the final frame into the business state, then clear the frame.

**Step 4: Run focused verification**

Run: `cd frontend; npm test -- workflowDragFrame workflowDesignerAutoLayout workflowEdgePath workflowViewport workflowDragViews`

Expected: all selected tests pass.

**Step 5: Run full verification**

Run: `cd frontend; npm test; npm run build`

Expected: all tests pass and Vite exits with code 0.

**Step 6: Commit**

```powershell
git add frontend/src/utils/workflowDragFrame.js frontend/src/utils/workflowDragFrame.test.mjs frontend/scripts/run-tests.mjs frontend/src/components/WorkflowDesigner.vue frontend/src/components/workflowDesignerAutoLayout.test.mjs
git commit -m "fix: render workflow drag frames atomically"
```
