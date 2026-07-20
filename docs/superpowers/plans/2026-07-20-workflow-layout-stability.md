# Workflow Layout Stability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make workflow templates render as readable state-change diagrams, keep same-state action buttons visible without self-loop lines, stabilize node dragging, and remove duplicate disabled template states without breaking historical references.

**Architecture:** Add pure frontend projection and drag-view modules so workflow business data remains unchanged while the canvas renders state-change edges and node-local action buttons differently. Extend the existing layout utility to use weak connectivity and a dedicated disabled-state lane. Reconcile template states by semantic identity on the backend, then run a transactional Alembic cleanup that remaps every known reference before deleting duplicate disabled states.

**Tech Stack:** Vue 3 Composition API, Element Plus, SVG, JavaScript ES modules, Node `assert`, FastAPI, SQLAlchemy, Alembic, Pytest, MySQL

---

## File Map

- Create `frontend/src/utils/workflowCanvasProjection.js`: partition states and transitions for canvas rendering without mutating workflow data.
- Create `frontend/src/utils/workflowCanvasProjection.test.mjs`: projection, node-action ordering, invalid endpoint, and disabled-state tests.
- Create `frontend/src/utils/workflowDragViews.js`: capture and combine stable full routes with incident-edge previews.
- Create `frontend/src/utils/workflowDragViews.test.mjs`: path stability and drag snapshot tests.
- Modify `frontend/src/utils/workflowAutoLayout.js`: weakly connected main graph, secondary root anchoring, variable row heights, and disabled-state region.
- Modify `frontend/src/utils/workflowAutoLayout.test.mjs`: default requirement graph, disabled lane, and deterministic layout tests.
- Modify `frontend/src/components/WorkflowDesigner.vue`: node action chips, details drawer, drag snapshots, and viewport freeze.
- Modify `frontend/src/components/workflowDesignerAutoLayout.test.mjs`: component source contracts for rendering and drag lifecycle.
- Modify `frontend/src/utils/workflowViewport.js`: include node-action rectangles in canvas content bounds.
- Modify `frontend/src/utils/workflowViewport.test.mjs`: node-action canvas bounds and stable viewport tests.
- Modify `backend/app/services/workflow_definition_service.py`: reuse unique semantic state matches during template application.
- Modify `backend/tests/test_workflow_definition_api.py`: idempotent template application and state ID reuse tests.
- Create `backend/alembic/versions/20260720_001_deduplicate_disabled_workflow_states.py`: transactional reference migration and duplicate-state deletion.
- Create `backend/tests/test_workflow_state_deduplication_migration.py`: migration planning, ambiguity, JSON remap, and SQL execution tests.

## Task 1: Project Workflow Data into Canvas Concepts

**Files:**
- Create: `frontend/src/utils/workflowCanvasProjection.js`
- Create: `frontend/src/utils/workflowCanvasProjection.test.mjs`
- Modify: `frontend/scripts/run-tests.mjs`

- [ ] **Step 1: Write failing projection tests**

Add tests that define enabled, disabled, invalid, state-changing, and same-state transitions:

```js
import assert from 'node:assert/strict'
import { projectWorkflowCanvas } from './workflowCanvasProjection.js'

const states = [
  { id: 1, status_name: '待分派', enabled: true, sort_order: 10 },
  { id: 2, status_name: '处理中', enabled: true, sort_order: 20 },
  { id: 3, status_name: '旧待分派', enabled: false, sort_order: 30 }
]
const transitions = [
  { id: 11, from_state_id: 1, to_state_id: 2, action_name: '认领', sort_order: 10 },
  { id: 12, from_state_id: 1, to_state_id: 1, action_name: '编辑', sort_order: 20 },
  { id: 13, from_state_id: 1, to_state_id: 1, action_name: '补充信息', sort_order: 30 },
  { id: 14, from_state_id: 99, to_state_id: 1, action_name: '无效', sort_order: 40 }
]

const result = projectWorkflowCanvas(states, transitions)
assert.deepEqual(result.activeStates.map((item) => item.id), [1, 2])
assert.deepEqual(result.inactiveStates.map((item) => item.id), [3])
assert.deepEqual(result.routedTransitions.map((item) => item.id), [11])
assert.deepEqual(result.stateActionsByStateId.get(1).map((item) => item.id), [12, 13])
assert.equal(result.stateActionsByStateId.has(99), false)
assert.equal(result.routedTransitions[0], transitions[0])
```

Also assert deterministic ordering by `sort_order` then ID, input immutability, and an empty result for empty input.

- [ ] **Step 2: Register and run the focused test to verify RED**

Add `workflowCanvasProjection.test.mjs` to the frontend test runner discovery list, then run:

```powershell
cd frontend
npm test -- workflowCanvasProjection
```

Expected: FAIL because `workflowCanvasProjection.js` does not exist.

- [ ] **Step 3: Implement the pure projection**

Create:

```js
export function projectWorkflowCanvas(states, transitions) {
  const stateIds = new Set(states.map((state) => state.id))
  const activeStates = states.filter((state) => state.enabled !== false)
  const inactiveStates = states.filter((state) => state.enabled === false)
  const validTransitions = transitions
    .filter((item) => stateIds.has(item.from_state_id) && stateIds.has(item.to_state_id))
    .sort(compareTransitions)
  const routedTransitions = validTransitions.filter((item) => item.from_state_id !== item.to_state_id)
  const stateActionsByStateId = new Map(states.map((state) => [state.id, []]))
  validTransitions
    .filter((item) => item.from_state_id === item.to_state_id)
    .forEach((item) => stateActionsByStateId.get(item.from_state_id).push(item))
  return { activeStates, inactiveStates, routedTransitions, stateActionsByStateId }
}
```

Implement `compareTransitions` with finite `sort_order` normalization and numeric/string ID fallback matching existing workflow utilities.

- [ ] **Step 4: Run focused and full frontend tests**

```powershell
cd frontend
npm test -- workflowCanvasProjection
npm test
```

Expected: both commands exit 0.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/utils/workflowCanvasProjection.js frontend/src/utils/workflowCanvasProjection.test.mjs frontend/scripts/run-tests.mjs
git commit -m "feat: project workflow canvas actions"
```

## Task 2: Produce a Two-Row Weakly Connected Layout

**Files:**
- Modify: `frontend/src/utils/workflowAutoLayout.js`
- Modify: `frontend/src/utils/workflowAutoLayout.test.mjs`

- [ ] **Step 1: Add the default requirement graph as a failing layout test**

Use five states and the state-changing subset of the default requirement template:

```js
const result = layoutWorkflowNodes(
  [
    state(1, 10, { status_name: '待分派', enabled: true }),
    state(2, 20, { status_name: '处理中', enabled: true }),
    state(3, 30, { status_name: '待确认', enabled: true }),
    state(4, 40, { status_name: '已完成', enabled: true, category: 'terminal' }),
    state(5, 50, { status_name: '已取消', enabled: true, category: 'terminal' })
  ],
  [
    transition(1, 2), transition(2, 4), transition(1, 5),
    transition(2, 5), transition(3, 5), transition(5, 1), transition(4, 1),
    transition(2, 2), transition(3, 3)
  ],
  1
)

assert.equal(byId(result, 1).x, WORKFLOW_LAYOUT.marginX)
assert.equal(byId(result, 2).x, byId(result, 3).x)
assert.equal(byId(result, 4).x, byId(result, 5).x)
assert.ok(byId(result, 1).x < byId(result, 2).x)
assert.ok(byId(result, 2).x < byId(result, 4).x)
assert.notEqual(byId(result, 2).y, byId(result, 3).y)
assert.notEqual(byId(result, 4).y, byId(result, 5).y)
```

Add disabled states and assert that every disabled state is below the maximum active-state bottom and has stable horizontal ordering. Add action-heavy nodes and assert same-layer row extents do not overlap when each action consumes `30px`.

- [ ] **Step 2: Run the focused test to verify RED**

```powershell
cd frontend
npm test -- workflowAutoLayout
```

Expected: FAIL because `待确认` is placed in a separate region/column and disabled nodes are not isolated by state activity.

- [ ] **Step 3: Replace directed reachability with weak main-component selection**

Change main region creation to:

```js
const activeIds = new Set(nodeIds.filter((id) => nodesById.get(id).enabled !== false))
const mainIds = collectWeakComponent(effectiveInitialId, outgoing, incoming, new Set(), activeIds)
```

Extend `collectWeakComponent` with an optional allowed-ID set and exclude self-loops from layer adjacency.

- [ ] **Step 4: Anchor secondary roots before their targets**

After the existing topological pass, adjust roots other than the preferred root:

```js
for (const rootId of roots) {
  if (rootId === preferredRootId) continue
  const targetLevels = keptOutgoing.get(rootId)
    .map((targetId) => levelById.get(targetId))
    .filter((level) => Number.isFinite(level) && level > 0)
  if (targetLevels.length) levelById.set(rootId, Math.max(0, Math.min(...targetLevels) - 1))
}
```

Run a bounded forward relaxation after this adjustment so downstream targets remain to the right.

- [ ] **Step 5: Add variable row extents and a disabled-state region**

Count same-state actions for each node. Use node row height:

```js
const rowHeight = (id) => 42 + selfActionCount.get(id) * 30 + 36
```

Place rows using cumulative heights instead of `row * rowGap`. After all active regions, place disabled states in a stable grid beginning at `activeBottom + WORKFLOW_LAYOUT.disabledRegionGap`. Export layout constants for `nodeHeight`, `actionHeight`, `actionGap`, and `disabledRegionGap`.

- [ ] **Step 6: Run focused and viewport regressions**

```powershell
cd frontend
npm test -- workflowAutoLayout workflowViewport workflowEdgePath
```

Expected: all focused tests pass and all returned coordinates are deterministic.

- [ ] **Step 7: Commit**

```powershell
git add frontend/src/utils/workflowAutoLayout.js frontend/src/utils/workflowAutoLayout.test.mjs frontend/src/utils/workflowViewport.test.mjs
git commit -m "fix: organize complete workflow components"
```

## Task 3: Keep Unrelated Edges Stable During Node Dragging

**Files:**
- Create: `frontend/src/utils/workflowDragViews.js`
- Create: `frontend/src/utils/workflowDragViews.test.mjs`
- Modify: `frontend/scripts/run-tests.mjs`

- [ ] **Step 1: Write failing drag-view tests**

```js
import assert from 'node:assert/strict'
import { combineWorkflowDragViews } from './workflowDragViews.js'

const full = [
  { key: 'a', transition: { from_state_id: 1, to_state_id: 2 }, path: 'FULL-A' },
  { key: 'b', transition: { from_state_id: 2, to_state_id: 3 }, path: 'FULL-B' },
  { key: 'c', transition: { from_state_id: 4, to_state_id: 5 }, path: 'FULL-C' }
]
const preview = [
  { key: 'a', transition: full[0].transition, path: 'PREVIEW-A' },
  { key: 'b', transition: full[1].transition, path: 'PREVIEW-B' },
  { key: 'c', transition: full[2].transition, path: 'PREVIEW-C' }
]

const result = combineWorkflowDragViews(full, preview, 2)
assert.deepEqual(result.map((item) => item.path), ['PREVIEW-A', 'PREVIEW-B', 'FULL-C'])
assert.deepEqual(combineWorkflowDragViews(full, preview, null), full)
```

Also cover missing snapshot keys (use preview), duplicate keys, deterministic order, and input immutability.

- [ ] **Step 2: Register and run the focused test to verify RED**

```powershell
cd frontend
npm test -- workflowDragViews
```

Expected: FAIL because the module does not exist.

- [ ] **Step 3: Implement bounded merge logic**

```js
export function combineWorkflowDragViews(fullViews, previewViews, draggedStateId) {
  if (draggedStateId == null) return fullViews
  const fullByKey = new Map(fullViews.map((view) => [view.key, view]))
  return previewViews.map((preview) => {
    const incident = preview.transition.from_state_id === draggedStateId ||
      preview.transition.to_state_id === draggedStateId
    return incident ? preview : (fullByKey.get(preview.key) || preview)
  })
}
```

- [ ] **Step 4: Run focused and full tests**

```powershell
cd frontend
npm test -- workflowDragViews
npm test
```

Expected: both commands pass.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/utils/workflowDragViews.js frontend/src/utils/workflowDragViews.test.mjs frontend/scripts/run-tests.mjs
git commit -m "fix: stabilize workflow drag previews"
```

## Task 4: Render Node Actions and Move Details into a Drawer

**Files:**
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Modify: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`
- Modify: `frontend/src/utils/workflowViewport.js`
- Modify: `frontend/src/utils/workflowViewport.test.mjs`

- [ ] **Step 1: Add failing component contracts**

Assert the component imports and uses the projection and drag helpers:

```js
assert.match(source, /import \{ projectWorkflowCanvas \} from '\.\.\/utils\/workflowCanvasProjection'/)
assert.match(source, /import \{ combineWorkflowDragViews \} from '\.\.\/utils\/workflowDragViews'/)
assert.match(source, /const canvasProjection = computed/)
assert.match(source, /buildWorkflowEdgeViews\(states\.value, canvasProjection\.value\.routedTransitions/)
assert.match(source, /v-for="action in nodeActionViews"/)
assert.match(source, /@click\.stop="selectTransition\(action\.transition\)"/)
assert.doesNotMatch(source, /<aside class="workflow-config-panel">/)
assert.match(source, /<el-drawer[\s\S]*workflow-details-drawer/)
```

Add drag lifecycle contracts requiring snapshot capture before `dragging.state` is assigned, `combineWorkflowDragViews`, frozen canvas edge views, and no `clampCurrentViewport()` call inside `stopDrag`.

- [ ] **Step 2: Run focused component tests to verify RED**

```powershell
cd frontend
npm test -- workflowDesignerAutoLayout workflowViewport
```

Expected: FAIL on missing projection, action rendering, drawer, and drag freeze contracts.

- [ ] **Step 3: Wire projected state-change edges**

Add:

```js
const canvasProjection = computed(() => projectWorkflowCanvas(states.value, transitions.value))
const routedTransitions = computed(() => canvasProjection.value.routedTransitions)
const fullTransitionViews = computed(() => (
  buildWorkflowEdgeViews(states.value, routedTransitions.value, transitionKey)
))
const previewTransitionViews = computed(() => (
  buildWorkflowEdgePreviewViews(states.value, routedTransitions.value, transitionKey)
))
```

Self-state transitions must remain in `transitions.value` for save/runtime semantics.

- [ ] **Step 4: Render node action chips**

Build stable action views from each node coordinate:

```js
const nodeActionViews = computed(() => states.value.flatMap((state) => (
  (canvasProjection.value.stateActionsByStateId.get(state.id) || []).map((transition, index) => ({
    key: transitionKey(transition),
    transition,
    x: state.x + 19,
    y: state.y + 50 + index * 30,
    width: 80,
    height: 24
  }))
)))
```

Render SVG `<g>` elements with 80x24 rects and centered text. Use `role="button"`, `tabindex="0"`, click selection, Enter/Space keyboard selection, stable dimensions, and selected styling.

- [ ] **Step 5: Replace the fixed right panel with a details drawer**

Wrap the existing state and transition basic forms in:

```vue
<el-drawer
  v-model="detailsDrawerVisible"
  class="workflow-details-drawer"
  direction="rtl"
  size="420px"
  :append-to-body="false"
  :lock-scroll="false"
  @closed="clearSelection"
>
```

`selectState` and `selectTransition` set selection and open the drawer. Keep the existing advanced configuration entry and `WorkflowAdvancedConfigDrawer`; opening advanced configuration closes the basic drawer only after pending basic bindings are already applied to the in-memory object.

- [ ] **Step 6: Freeze drag routes, canvas bounds, and viewport**

Extend drag state:

```js
const dragging = reactive({
  state: null,
  startX: 0,
  startY: 0,
  originX: 0,
  originY: 0,
  edgeViews: [],
  canvasEdges: []
})
```

In `startDrag`, copy `fullTransitionViews.value` into both snapshots before assigning `dragging.state`. During drag, use `combineWorkflowDragViews`. Use `dragging.canvasEdges` for `workflowCanvasSize`. In `stopDrag`, clear snapshots after setting `dragging.state = null`, but do not call `clampCurrentViewport`.

Guard the canvas-size watcher with a one-tick `suppressCanvasClamp` flag during drag completion so the restored full bounds do not move `viewportOffset`.

- [ ] **Step 7: Include action chips in canvas bounds**

Extend `workflowCanvasSize` with an optional `extraRectangles` argument and include node action rectangles in content bounds. Add tests showing a node with three actions expands the canvas bottom and that an unchanged viewport offset remains valid.

- [ ] **Step 8: Run focused and full frontend tests**

```powershell
cd frontend
npm test -- workflowCanvasProjection workflowDragViews workflowAutoLayout workflowDesignerAutoLayout workflowViewport workflowEdgePath
npm test
npm run build
```

Expected: all tests pass; build emits only existing VueUse PURE and large-chunk warnings.

- [ ] **Step 9: Commit**

```powershell
git add frontend/src/components/WorkflowDesigner.vue frontend/src/components/workflowDesignerAutoLayout.test.mjs frontend/src/utils/workflowViewport.js frontend/src/utils/workflowViewport.test.mjs
git commit -m "feat: clarify workflow canvas interactions"
```

## Task 5: Reuse Existing States When Applying Templates

**Files:**
- Modify: `backend/app/services/workflow_definition_service.py`
- Modify: `backend/tests/test_workflow_definition_api.py`

- [ ] **Step 1: Add a failing idempotent-template API test**

Create a requirement definition, apply the template, record `{status_name: id}`, apply it again, and assert:

```python
first = client.post(f"/api/v1/workflow-definitions/{definition_id}/apply-template")
second = client.post(f"/api/v1/workflow-definitions/{definition_id}/apply-template")

assert first.status_code == 200
assert second.status_code == 200
assert {item["status_name"]: item["id"] for item in second.json()["states"] if item["enabled"]} == {
    item["status_name"]: item["id"] for item in first.json()["states"] if item["enabled"]
}
assert len([item for item in second.json()["states"] if item["enabled"]]) == 5
```

Add a case with one disabled matching state and assert it is reused and re-enabled. Add an ambiguous duplicate-match case and assert a 422 response rather than an arbitrary match.

- [ ] **Step 2: Run the API tests to verify RED**

```powershell
cd backend
E:\miniforge3\python.exe -m pytest tests/test_workflow_definition_api.py -k "template and reuse" -q
```

Expected: FAIL because applying the template creates new state IDs.

- [ ] **Step 3: Implement deterministic template state matching**

In `_template_graph_payload`, load existing definition states and match each template state by `(status_name, category)`:

```python
existing_by_identity: dict[tuple[str, str], list[WorkflowState]] = defaultdict(list)
for state in db.query(WorkflowState).filter(WorkflowState.definition_id == definition.id).all():
    existing_by_identity[(state.status_name, state.category)].append(state)

matches = existing_by_identity[(item.status_name, item.category)]
enabled_matches = [state for state in matches if state.enabled]
candidate = enabled_matches[0] if len(enabled_matches) == 1 else None
if candidate is None and not enabled_matches and len(matches) == 1:
    candidate = matches[0]
if len(enabled_matches) > 1 or (not enabled_matches and len(matches) > 1):
    raise HTTPException(status_code=422, detail=f"Ambiguous template state: {item.status_name}")
input_id = candidate.id if candidate else next_temp_id
```

Template state data sets `enabled=True`, so a uniquely matched disabled state is re-enabled. Keep negative IDs only for genuinely new states.

- [ ] **Step 4: Run focused and full backend tests**

```powershell
cd backend
E:\miniforge3\python.exe -m pytest tests/test_workflow_definition_api.py -k "template" -q
E:\miniforge3\python.exe -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/services/workflow_definition_service.py backend/tests/test_workflow_definition_api.py
git commit -m "fix: reuse workflow template states"
```

## Task 6: Migrate References and Delete Disabled Duplicates

**Files:**
- Create: `backend/alembic/versions/20260720_001_deduplicate_disabled_workflow_states.py`
- Create: `backend/tests/test_workflow_state_deduplication_migration.py`

- [ ] **Step 1: Write failing migration helper tests**

Load the migration module with `importlib.util.spec_from_file_location`. Test a pure planner:

```python
states = [
    {"id": 10, "definition_id": 7, "status_name": "待分派", "enabled": 1},
    {"id": 11, "definition_id": 7, "status_name": "待分派", "enabled": 0},
]
assert migration._plan_duplicate_state_merges(states) == {11: 10}
```

Assert the planner skips zero active matches, skips multiple active matches, never merges across definitions, and produces stable sorted diagnostics. Test `_remap_condition_config` for `routes` and `target_state_id_by_owner` without changing unrelated integers.

- [ ] **Step 2: Run migration tests to verify RED**

```powershell
cd backend
E:\miniforge3\python.exe -m pytest tests/test_workflow_state_deduplication_migration.py -q
```

Expected: FAIL because the migration module does not exist.

- [ ] **Step 3: Implement the migration planner and reference updates**

Create revision `20260720_001` with down revision `20260717_002`.

Implement `_plan_duplicate_state_merges(states)` returning `{disabled_id: unique_enabled_id}` only for a unique active state with the same `(definition_id, status_name)`. In `upgrade()` execute all work on `op.get_bind()`:

```python
for old_id, new_id in merges.items():
    for table in ("requirements", "tasks", "bugs", "projects", "iterations"):
        bind.execute(sa.text(
            f"UPDATE {table} SET current_state_id = :new_id WHERE current_state_id = :old_id"
        ), {"new_id": new_id, "old_id": old_id})
    bind.execute(sa.text(
        "UPDATE status_operation_logs SET from_state_id = :new_id WHERE from_state_id = :old_id"
    ), {"new_id": new_id, "old_id": old_id})
    bind.execute(sa.text(
        "UPDATE status_operation_logs SET to_state_id = :new_id WHERE to_state_id = :old_id"
    ), {"new_id": new_id, "old_id": old_id})
    bind.execute(sa.text(
        "UPDATE workflow_definitions SET initial_state_id = :new_id WHERE initial_state_id = :old_id"
    ), {"new_id": new_id, "old_id": old_id})
    bind.execute(sa.text(
        "UPDATE workflow_transitions SET from_state_id = :new_id WHERE from_state_id = :old_id"
    ), {"new_id": new_id, "old_id": old_id})
    bind.execute(sa.text(
        "UPDATE workflow_transitions SET to_state_id = :new_id WHERE to_state_id = :old_id"
    ), {"new_id": new_id, "old_id": old_id})
```

Load each non-null `condition_config`, remap only state-reference dictionaries, and update JSON through SQLAlchemy JSON serialization. Before deletion, run a reference audit across these columns. Delete only IDs with zero remaining references. `downgrade()` is a documented no-op because deleted duplicate identities cannot be reconstructed safely.

- [ ] **Step 4: Add execution-level fake-bind tests**

Use a recording bind or temporary SQLite schema to assert every reference table is updated before the delete statement, ambiguous groups emit diagnostics and are not deleted, JSON remapping is persisted, and an audit failure raises before deletion.

- [ ] **Step 5: Run focused migration and backend tests**

```powershell
cd backend
E:\miniforge3\python.exe -m pytest tests/test_workflow_state_deduplication_migration.py -q
E:\miniforge3\python.exe -m pytest tests/test_workflow_state_migration.py tests/test_project_iteration_state_migration.py -q
E:\miniforge3\python.exe -m pytest -q
E:\miniforge3\python.exe -m alembic heads
```

Expected: all tests pass and the only head is `20260720_001`.

- [ ] **Step 6: Commit**

```powershell
git add backend/alembic/versions/20260720_001_deduplicate_disabled_workflow_states.py backend/tests/test_workflow_state_deduplication_migration.py
git commit -m "fix: remove duplicate disabled workflow states"
```

## Task 7: Apply the Migration and Perform End-to-End Verification

**Files:**
- Modify only if a verified defect requires it: files from Tasks 1-6.

- [ ] **Step 1: Capture a read-only pre-migration audit**

Run a query that records duplicate disabled state IDs, their unique enabled targets, and reference counts for current business items and operation logs. Confirm the current `cfg` requirement definition contains the expected three duplicate disabled states and every one has a unique active target.

- [ ] **Step 2: Run the migration against the configured database**

```powershell
cd backend
E:\miniforge3\python.exe -m alembic upgrade head
```

Expected: exit 0 with revision `20260720_001` applied.

- [ ] **Step 3: Verify database cleanup without changing business meaning**

Query the `cfg` requirement definition and assert:

- exactly five states remain;
- no disabled duplicate state remains;
- the existing requirement formerly referencing disabled “已完成” now references active “已完成”;
- operation-log state IDs reference existing states;
- requirement/task/bug graph transition counts remain 19/20/26.

- [ ] **Step 4: Start the worktree frontend on an unused port**

Keep the existing backend on `8000`. Start Vite from this worktree on `5174`:

```powershell
cd frontend
npm run dev -- --port 5174
```

Expected: `http://127.0.0.1:5174/` returns 200.

- [ ] **Step 5: Browser acceptance for `cfg`**

Using `browser:control-in-app-browser`, open the `cfg` workflow scheme and verify requirement, task, and Bug graphs:

- only state-changing transitions render as lines;
- same-state action buttons render under their states and open the matching transition drawer;
- disabled states use white/gray dashed styling in the disabled region when present;
- “整理布局” produces a readable multi-row graph;
- dragging a node keeps non-incident edge `d` attributes and the viewport `<g transform>` unchanged during the drag;
- mouseup does not change the viewport transform;
- explicit “适应视图” still recenters;
- no save request occurs during organization or drag verification.

Capture before/after screenshots at 1440x900 and inspect for overlaps, clipped action chips, off-screen labels, or incoherent return routes.

- [ ] **Step 6: Run final verification**

```powershell
cd frontend
npm test
npm run build
cd ..\backend
E:\miniforge3\python.exe -m pytest -q
cd ..
git diff --check
git status --short
```

Expected: all tests and build pass, `git diff --check` is clean, and only intentional files are committed.

- [ ] **Step 7: Commit verified fixes if browser QA required changes**

Stage only files changed to fix a reproduced QA defect:

```powershell
git add frontend/src backend/app backend/alembic backend/tests
git commit -m "fix: refine workflow layout stability"
```

Skip this commit if the worktree is already clean.

## Final Review Checklist

- [ ] Every same-state transition remains in the save payload and runtime model.
- [ ] No same-state transition is routed as an SVG self-loop.
- [ ] Disabled states remain selectable and re-enableable unless removed by the approved duplicate cleanup.
- [ ] The default requirement graph uses the approved two-row structure.
- [ ] Dragging never changes the viewport automatically.
- [ ] Template application is idempotent for state IDs.
- [ ] Migration updates all known state references before deletion.
- [ ] Ambiguous migrations are skipped with deterministic diagnostics.
- [ ] Full frontend tests, backend tests, production build, browser checks, and Git integrity checks pass.
