# Workflow Auto Layout Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add deterministic workflow graph organization that runs after template application and from a manual toolbar button, while routing complex edges into readable separate tracks.

**Architecture:** Keep `WorkflowDesigner.vue` as the interaction and persistence boundary. Add a pure layout utility for graph analysis and node coordinates, and change the edge utility from isolated per-edge routing to whole-graph route allocation; neither utility mutates workflow business data. Continue using the existing Vue + SVG renderer and existing graph save API.

**Tech Stack:** Vue 3 Composition API, JavaScript ES modules, SVG paths, Element Plus, Node `assert` tests, Vite

---

Implementation must follow @superpowers:test-driven-development. Before reporting completion, use @superpowers:verification-before-completion. Use @frontend-design for the toolbar interaction and visual QA while preserving the existing design system.

### Task 1: Deterministic Layered Node Layout

**Files:**
- Create: `frontend/src/utils/workflowAutoLayout.js`
- Create: `frontend/src/utils/workflowAutoLayout.test.mjs`

**Step 1: Write the failing layout tests**

Create table-driven tests that call:

```js
import { layoutWorkflowNodes } from './workflowAutoLayout.js'

const states = [
  { id: 1, sort_order: 10, x: 0, y: 0 },
  { id: 2, sort_order: 20, x: 0, y: 0 },
  { id: 3, sort_order: 30, x: 0, y: 0 },
  { id: 4, sort_order: 40, x: 0, y: 0 }
]
const transitions = [
  { id: 11, from_state_id: 1, to_state_id: 2, sort_order: 10 },
  { id: 12, from_state_id: 2, to_state_id: 3, sort_order: 20 },
  { id: 13, from_state_id: 3, to_state_id: 2, sort_order: 30 }
]

const result = layoutWorkflowNodes(states, transitions, 1)
assert.ok(result.find((item) => item.id === 1).x < result.find((item) => item.id === 2).x)
assert.ok(result.find((item) => item.id === 2).x < result.find((item) => item.id === 3).x)
assert.deepEqual(layoutWorkflowNodes(states, transitions, 1), result)
assert.equal(result.find((item) => item.id === 1).sort_order, 10)
```

Also cover:

- branch and merge nodes occupy stable layers without coordinate overlap;
- a back edge does not move its target into a later layer;
- disconnected nodes are placed below the connected graph;
- missing `initialStateId` falls back to zero-indegree then stable state order;
- invalid transition endpoints are ignored;
- empty input returns an empty array;
- every returned state preserves all fields except `x` and `y`;
- adjacent layer X positions differ by at least `240`, and same-layer Y positions differ by at least `120`.

**Step 2: Run the focused test and verify failure**

Run: `cd frontend; npm test -- workflowAutoLayout`

Expected: FAIL because `workflowAutoLayout.js` does not exist.

**Step 3: Implement the minimum layered layout utility**

Export:

```js
export const WORKFLOW_LAYOUT = Object.freeze({
  marginX: 80,
  marginY: 80,
  layerGap: 240,
  rowGap: 120
})

export function layoutWorkflowNodes(states, transitions, initialStateId) {
  // Return cloned state objects with deterministic x/y coordinates.
}
```

Implementation details:

1. Build stable state and adjacency maps using `sort_order`, then numeric/string ID as a tie-breaker.
2. Choose roots in this order: valid initial state, zero-indegree states, remaining states.
3. Use a queue to assign the first reachable depth. Ignore an edge that points to an already visited ancestor so cycles cannot increase depth indefinitely.
4. Run a bounded relaxation over non-back edges so merge nodes appear after all forward predecessors.
5. Group connected nodes by depth and place them at `marginX + depth * layerGap`.
6. Center each layer within the height of the tallest layer using `rowGap`.
7. Put disconnected components below the connected graph with the same stable ordering and spacing.
8. Return new objects; never mutate `states` or `transitions`.

Keep the utility dependency-free and independent from Vue.

**Step 4: Run the focused test and verify success**

Run: `cd frontend; npm test -- workflowAutoLayout`

Expected: PASS and print `workflow auto layout tests passed`.

**Step 5: Commit the layout utility**

```powershell
git add frontend/src/utils/workflowAutoLayout.js frontend/src/utils/workflowAutoLayout.test.mjs
git commit -m "feat: add workflow node auto layout"
```

### Task 2: Whole-Graph Edge Track Routing

**Files:**
- Modify: `frontend/src/utils/workflowEdgePath.js`
- Modify: `frontend/src/utils/workflowEdgePath.test.mjs`

**Step 1: Write failing whole-graph routing tests**

Retain existing `buildWorkflowEdgeView(from, to)` compatibility tests and add tests for:

```js
import { buildWorkflowEdgeViews } from './workflowEdgePath.js'

const views = buildWorkflowEdgeViews(states, transitions, (item) => item.id)
assert.equal(views.length, transitions.length)
assert.equal(new Set(views.map((item) => `${item.labelX}:${item.labelY}`)).size, views.length)
```

Test these cases explicitly:

- two transitions with the same source and target receive different tracks and label positions;
- forward edges connect right-to-left;
- a back edge routes below both endpoint nodes;
- a long edge skipping one or more layers does not intersect the skipped node rectangle;
- a self-loop returns a visible path outside its node;
- invalid endpoints are omitted;
- routing is deterministic and does not mutate states or transitions.

Add a small segment-versus-rectangle assertion helper in the test so node avoidance is verified geometrically, not by fragile full-path snapshots.

**Step 2: Run the focused test and verify failure**

Run: `cd frontend; npm test -- workflowEdgePath`

Expected: FAIL because `buildWorkflowEdgeViews` is not exported or routes overlap.

**Step 3: Implement whole-graph route allocation**

Export:

```js
export function buildWorkflowEdgeViews(states, transitions, transitionKey) {
  // Resolve endpoints, classify edges, allocate tracks, and return view objects.
}
```

Each returned item must have:

```js
{
  key,
  transition,
  path,
  labelX,
  labelY,
  start,
  end
}
```

Routing rules:

1. Sort transitions stably by endpoint IDs, `sort_order`, and key before assigning track indexes.
2. Route ordinary forward edges right-to-left through a midpoint track.
3. Offset duplicate endpoint-pair tracks by `28px` so paths and labels remain distinct.
4. Route back edges beneath the lowest endpoint with increasing `36px` track offsets.
5. Route self-loops outside the node's right and lower sides.
6. For long forward edges, move the horizontal track above or below any intervening node rectangle, including a `20px` clearance.
7. Keep `roundedPolylinePath` as the renderer so visual styling remains consistent.
8. Keep `buildWorkflowEdgeView` as a thin compatibility wrapper for existing callers/tests until the component switches to the whole-graph API.

**Step 4: Run the focused routing tests and verify success**

Run: `cd frontend; npm test -- workflowEdgePath`

Expected: PASS and print `workflowEdgePath tests passed`.

**Step 5: Commit the routing change**

```powershell
git add frontend/src/utils/workflowEdgePath.js frontend/src/utils/workflowEdgePath.test.mjs
git commit -m "feat: separate workflow edge routes"
```

### Task 3: Designer Integration and Interaction

**Files:**
- Modify: `frontend/src/components/WorkflowDesigner.vue:20-28`
- Modify: `frontend/src/components/WorkflowDesigner.vue:267-274`
- Modify: `frontend/src/components/WorkflowDesigner.vue:326-353`
- Modify: `frontend/src/components/WorkflowDesigner.vue:547-551`
- Create: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`

**Step 1: Write the failing component contract test**

Read `WorkflowDesigner.vue` as UTF-8 and assert that it contains:

```js
assert.match(source, /import \{ layoutWorkflowNodes \} from '\.\.\/utils\/workflowAutoLayout'/)
assert.match(source, /import \{ buildWorkflowEdgeViews \} from '\.\.\/utils\/workflowEdgePath'/)
assert.match(source, />\s*整理布局\s*</)
assert.match(source, /async function organizeLayout\(\)/)
assert.match(source, /ElMessageBox\.confirm\('整理布局将重新排列全部节点/)
assert.match(source, /applyGraph\(graph\.data, \{ organize: true \}\)/)
assert.match(source, /layoutWorkflowNodes\(states\.value, transitions\.value, initialStateId\.value\)/)
assert.match(source, /buildWorkflowEdgeViews\(states\.value, transitions\.value, transitionKey\)/)
```

Also assert that the ordinary load and save paths still call `applyGraph(graph.data)` without `organize: true`, so reopening or saving does not overwrite a persisted manual layout.

**Step 2: Run the focused test and verify failure**

Run: `cd frontend; npm test -- workflowDesignerAutoLayout`

Expected: FAIL because the button, imports, and integration functions do not exist.

**Step 3: Integrate the route builder**

Replace the per-transition computed mapping with:

```js
const transitionViews = computed(() => (
  buildWorkflowEdgeViews(states.value, transitions.value, transitionKey)
))
```

Do not change SVG edge rendering or selection behavior.

**Step 4: Integrate automatic template organization**

Change `applyGraph` to accept an optional flag:

```js
function applyGraph(graph, { organize = false } = {}) {
  // Existing graph normalization.
  if (organize) applyOrganizedLayout()
  fitToContent()
}
```

In `applyTemplate`, call `applyGraph(graph.data, { organize: true })`. Keep normal load and save responses unchanged so persisted user coordinates survive reopening and saving.

**Step 5: Add manual organization behavior**

Add a toolbar button between “新增流转” and “适应视图”:

```vue
<el-button size="small" @click="organizeLayout">整理布局</el-button>
```

Implement:

```js
function applyOrganizedLayout() {
  states.value = layoutWorkflowNodes(states.value, transitions.value, initialStateId.value)
}

async function organizeLayout() {
  if (!states.value.length) {
    ElMessage.info('当前没有可整理的状态节点')
    return
  }
  await ElMessageBox.confirm(
    '整理布局将重新排列全部节点，确认继续？',
    '整理布局',
    { type: 'warning' }
  )
  applyOrganizedLayout()
  fitToContent()
}
```

Do not call `saveGraph`, the graph API, or mutate transition configuration from either function.

**Step 6: Run focused component and utility tests**

Run: `cd frontend; npm test -- workflowDesignerAutoLayout workflowAutoLayout workflowEdgePath workflowViewport`

Expected: PASS for all selected files.

**Step 7: Commit the component integration**

```powershell
git add frontend/src/components/WorkflowDesigner.vue frontend/src/components/workflowDesignerAutoLayout.test.mjs
git commit -m "feat: organize workflow layouts"
```

### Task 4: Regression and Visual Verification

**Files:**
- Modify only if a real defect is found: `frontend/src/utils/workflowAutoLayout.js`
- Modify only if a real defect is found: `frontend/src/utils/workflowEdgePath.js`
- Modify only if a real defect is found: `frontend/src/components/WorkflowDesigner.vue`

**Step 1: Run the complete frontend test suite**

Run: `cd frontend; npm test`

Expected: PASS with no failed `.test.mjs` file.

**Step 2: Run the production build**

Run: `cd frontend; npm run build`

Expected: exit code 0 and a generated `dist` build.

**Step 3: Start the existing backend and frontend development servers**

Use the repository's documented commands and available Python environment. Reuse already-running healthy servers; otherwise start backend on `http://127.0.0.1:8000` and Vite on `http://127.0.0.1:5173`.

Expected: both health/navigation checks respond successfully.

**Step 4: Perform browser interaction acceptance at 1440x900**

Use @browser:control-in-app-browser and verify:

1. Open a workflow scheme and each of requirement, task, and Bug definitions.
2. Click “套用模板”, accept the warning, and confirm nodes automatically spread into readable layers.
3. Confirm duplicate, reverse, and long edges have visibly separate paths and labels do not cover nodes.
4. Drag one node, click “整理布局”, cancel, and confirm coordinates do not change.
5. Click “整理布局” again, confirm, and verify all nodes are rearranged and the view fits the content.
6. Reload without saving and confirm the manual organization was not persisted.
7. Organize again, save the graph, reload, and confirm coordinates persist.
8. Confirm state/transition selection, dragging, advanced configuration, and graph saving still work.

Capture a screenshot after template auto-organization and after manual organization. Inspect for node overlap, label overlap, clipped content, incoherent edge crossings, or horizontal page overflow.

**Step 5: Re-run verification after any visual fix**

Run:

```powershell
cd frontend
npm test -- workflowAutoLayout workflowEdgePath workflowDesignerAutoLayout
npm run build
```

Expected: all commands PASS after the final code change.

**Step 6: Commit only necessary verification fixes**

```powershell
git add frontend/src/utils/workflowAutoLayout.js frontend/src/utils/workflowEdgePath.js frontend/src/components/WorkflowDesigner.vue frontend/src/**/*.test.mjs
git commit -m "fix: refine workflow layout readability"
```

Skip this commit when visual verification requires no code changes.
