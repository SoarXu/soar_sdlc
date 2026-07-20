# Workflow Same-State Action Menu Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace vertically stacked same-state action buttons with one fixed “操作 N” trigger per state and an on-demand floating menu.

**Architecture:** Keep `projectWorkflowCanvas` as the source of same-state transitions and keep those transitions out of edge routing. The SVG canvas renders one fixed trigger per state, while a native HTML menu is positioned over the canvas from the trigger’s canvas coordinate plus the current viewport offset. Only the trigger participates in layout and canvas bounds; the floating menu never changes routing, canvas size, or viewport position.

**Tech Stack:** Vue 3 Composition API, Element Plus, SVG, JavaScript ES modules, Node `assert`, Vite

---

### Task 1: Give Every Action-Bearing Node One Fixed Layout Slot

**Files:**
- Modify: `frontend/src/utils/workflowAutoLayout.test.mjs`
- Modify: `frontend/src/utils/workflowAutoLayout.js`

**Step 1: Write the failing fixed-height layout test**

Add a test that lays out two otherwise identical graphs: one graph gives a node one self-transition, and the other gives the same node three self-transitions. Assert that the next row starts at the same `y` coordinate in both graphs.

```js
const oneAction = layoutWorkflowNodes(nodes, [transition(1, 1)], 1)
const threeActions = layoutWorkflowNodes(
  nodes,
  [transition(1, 1), transition(1, 1, { id: 2 }), transition(1, 1, { id: 3 })],
  1
)

assert.equal(byId(oneAction, 2).y, byId(threeActions, 2).y)
```

Also update the disabled-region assertion so an action-bearing node contributes exactly one `actionHeight + actionGap` slot regardless of action count.

**Step 2: Run the focused test to verify RED**

Run:

```powershell
cd frontend
npm test -- workflowAutoLayout
```

Expected: FAIL because `nodeBlockHeight` currently multiplies the action slot by every same-state transition.

**Step 3: Implement one-slot action occupancy**

Keep collecting self-transition counts, but normalize occupancy inside `nodeBlockHeight`:

```js
function nodeBlockHeight(id, selfActionCount) {
  const hasActions = (selfActionCount.get(id) || 0) > 0
  return WORKFLOW_LAYOUT.nodeHeight +
    (hasActions ? WORKFLOW_LAYOUT.actionHeight + WORKFLOW_LAYOUT.actionGap : 0)
}
```

Do not change state coordinates, disabled-region selection, weak-component grouping, or state-changing edge handling.

**Step 4: Run layout regressions**

Run:

```powershell
cd frontend
npm test -- workflowAutoLayout workflowViewport workflowEdgePath
```

Expected: all selected tests pass.

**Step 5: Commit**

```powershell
git add frontend/src/utils/workflowAutoLayout.js frontend/src/utils/workflowAutoLayout.test.mjs
git commit -m "fix: reserve one workflow action slot per state"
```

### Task 2: Replace Stacked Actions with a Trigger and Floating Menu

**Files:**
- Modify: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Modify: `frontend/src/utils/workflowViewport.test.mjs`

**Step 1: Write failing component contracts**

Replace the current stacked-action assertions with contracts requiring:

```js
assert.match(source, /v-for="trigger in nodeActionTriggers"/)
assert.match(source, /class="workflow-node-action-trigger"/)
assert.match(source, /操作 \{\{ trigger\.actions\.length \}\}/)
assert.match(source, /class="workflow-node-action-menu"/)
assert.match(source, /v-for="action in activeNodeActionMenu\.actions"/)
assert.match(source, /selectNodeAction\(action\)/)
assert.doesNotMatch(source, /v-for="action in nodeActionViews"/)
assert.match(source, /nodeActionTriggerBounds\.value/)
```

Add lifecycle contracts proving `closeNodeActionMenu()` is called by `clearSelection`, `startDrag`, `startViewportDrag`, and `applyGraph`.

Update the viewport source contract so `workflowCanvasSize` receives trigger bounds rather than one rectangle per action.

**Step 2: Run focused tests to verify RED**

Run:

```powershell
cd frontend
npm test -- workflowDesignerAutoLayout workflowViewport
```

Expected: FAIL because the component still renders `nodeActionViews` as one SVG group per action.

**Step 3: Build one trigger per state**

Replace `nodeActionViews` with:

```js
const nodeActionTriggers = computed(() => states.value.flatMap((state) => {
  const actions = canvasProjection.value.stateActionsByStateId.get(state.id) || []
  if (!actions.length) return []
  return [{
    stateId: state.id,
    actions,
    x: state.x + 19,
    y: state.y + 50,
    width: 80,
    height: 24
  }]
}))
```

Render one SVG trigger group per item. Its label is `操作 {{ trigger.actions.length }}`. Preserve fixed width and height, pointer and keyboard activation, and selected styling while its menu is open.

**Step 4: Add floating menu state and positioning**

Add:

```js
const activeNodeActionStateId = ref(null)
const activeNodeActionMenu = computed(() => (
  nodeActionTriggers.value.find((item) => item.stateId === activeNodeActionStateId.value) || null
))
```

Implement `toggleNodeActionMenu(trigger)`, `closeNodeActionMenu()`, and `selectNodeAction(transition)`. `selectNodeAction` closes the menu before calling the existing `selectTransition(transition)`.

Render the menu as a native HTML element inside `.workflow-canvas`, outside the SVG. Use `position: absolute` and compute screen coordinates from the trigger plus `viewportOffset`. Clamp horizontally to the canvas viewport; if the menu would exceed the bottom, place it above the trigger. Menu opening and closing must not update `states`, `transitions`, `canvasSize`, or `viewportOffset`.

Each menu item is a native button. Apply a disabled visual class when `transition.enabled === false`, but keep it clickable so the transition drawer can re-enable it. Allow action names to wrap within a stable menu width.

**Step 5: Close transient menus on canvas lifecycle events**

Call `closeNodeActionMenu()` before selection clearing, graph replacement, node drag, and viewport drag. Opening another node, edge, or transition drawer also closes the existing menu. Add Escape handling on the menu container.

Do not close the menu merely because `canvasSize` recomputes; the menu itself must never be part of that computation.

**Step 6: Include only trigger rectangles in canvas bounds**

Rename `nodeActionBounds` to `nodeActionTriggerBounds` and derive one rectangle per trigger:

```js
const nodeActionTriggerBounds = computed(() => nodeActionTriggers.value.map((trigger) => ({
  left: trigger.x,
  top: trigger.y,
  right: trigger.x + trigger.width,
  bottom: trigger.y + trigger.height
})))
```

Pass these bounds to `workflowCanvasSize`. Add a viewport test showing that one action and five actions on the same state produce the same extra rectangle and canvas bottom.

**Step 7: Style the trigger and menu**

Replace `.workflow-node-action` styles with:

- `.workflow-node-action-trigger` for the single SVG entry;
- `.workflow-node-action-menu` for the floating HTML surface;
- `.workflow-node-action-menu-item` for stable native buttons;
- `.inactive` for disabled transitions.

Use the existing neutral/blue workflow palette, an 80x24 trigger, a menu width that fits long Chinese labels, `8px` maximum radius, and a clear keyboard focus state. Do not add menu contents to SVG edge routing.

**Step 8: Run focused and full frontend verification**

Run:

```powershell
cd frontend
npm test -- workflowCanvasProjection workflowAutoLayout workflowDesignerAutoLayout workflowViewport workflowDragViews workflowEdgePath
npm test
npm run build
```

Expected: all tests pass; the build exits 0 with only existing VueUse PURE and chunk-size warnings.

**Step 9: Commit**

```powershell
git add frontend/src/components/WorkflowDesigner.vue frontend/src/components/workflowDesignerAutoLayout.test.mjs frontend/src/utils/workflowViewport.test.mjs
git commit -m "feat: collapse same-state actions into menus"
```

### Task 3: Browser Acceptance and Integration

**Files:**
- Modify only if a reproduced defect requires it: files from Tasks 1-2.

**Step 1: Start the feature frontend and current backend**

Use an isolated worktree for execution, then start Vite on an unused port while keeping the current backend on `8000`.

```powershell
cd frontend
npm run dev -- --port 5174
```

Expected: the selected localhost URL returns 200.

**Step 2: Verify the requirement workflow visually**

Open the `cfg` requirement workflow and assert:

- each action-bearing state shows exactly one “操作 N” trigger;
- no stacked same-state buttons remain;
- opening a menu does not move nodes, edges, or the viewport transform;
- the menu lists all same-state operations in stable order;
- a disabled operation is visibly distinct and still opens its transition drawer;
- clicking an action opens the matching drawer and closes the menu;
- clicking blank canvas, dragging a node, panning, and pressing Escape close the menu;
- long action names fit without clipping;
- state-changing edge labels remain readable.

Capture a 1440x900 screenshot with the menu closed and another with the busiest menu open. Check for overlaps at desktop and a narrow viewport.

**Step 3: Run final verification**

```powershell
cd frontend
npm test
npm run build
cd ..
git diff --check
git status --short
```

Expected: tests and build pass, `git diff --check` is clean, and only intentional commits exist in the feature branch.

**Step 4: Complete the development branch**

Use `@superpowers:finishing-a-development-branch` to present merge, PR, keep, or discard options. Do not include the user’s unrelated report modification in any commit.
