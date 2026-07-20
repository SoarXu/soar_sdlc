# Workflow Interactive Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace permanent same-state action boxes with node badges, make node dragging render the final route continuously, and support persistent manual endpoint and orthogonal-segment editing.

**Architecture:** Persist diagram-only geometry in a new `workflow_transitions.diagram_config` JSON column with strict backend validation. A focused frontend pure-function module owns anchors and orthogonal waypoint editing; `workflowEdgePath` projects automatic and manual transitions into the existing edge-view shape, while `WorkflowDesigner` coordinates pointer interactions and the existing drawer exposes reset-to-auto.

**Tech Stack:** Vue 3 Composition API, SVG, Element Plus, JavaScript ES modules with Node `assert`, FastAPI, Pydantic, SQLAlchemy, Alembic, pytest, Vite

---

## File Map

- Create `frontend/src/utils/workflowManualRoute.js`: validate, normalize, render, and edit manual orthogonal route geometry.
- Create `frontend/src/utils/workflowManualRoute.test.mjs`: pure-function coverage for anchors and segment edits.
- Modify `frontend/src/utils/workflowEdgePath.js`: project manual transitions using the same edge-view contract as automatic transitions.
- Modify `frontend/src/utils/workflowEdgePath.test.mjs`: mixed automatic/manual projection and label/bounds coverage.
- Modify `frontend/src/components/WorkflowDesigner.vue`: node badge, final-route drag loop, endpoints, segment hit targets, Escape rollback, and reset handling.
- Modify `frontend/src/components/WorkflowAdvancedConfigDrawer.vue`: display automatic/manual canvas routing status and emit reset.
- Modify component source-contract tests under `frontend/src/components/*.test.mjs` and viewport/layout tests under `frontend/src/utils/*.test.mjs`.
- Modify `backend/app/models/workflow_definition.py`: add the SQLAlchemy JSON column.
- Modify `backend/app/views/workflow_definition_view.py`: expose `diagram_config` in graph save/read types.
- Modify `backend/app/services/workflow_definition_service.py`: validate and persist versioned diagram geometry.
- Modify `backend/app/db/schema.py`: ensure the column for bootstrap-managed databases.
- Rename `backend/alembic/versions/20260720_001_normalize_workflow_transition_buttons.py` to `20260720_002_normalize_workflow_transition_buttons.py` and correct its revision chain.
- Create `backend/alembic/versions/20260720_003_add_workflow_transition_diagram_config.py`.
- Modify `backend/tests/test_workflow_definition_api.py`, `backend/tests/test_model_metadata.py`, and add a focused migration test.

### Task 1: Repair The Migration Chain And Persist Diagram Geometry

**Files:**
- Rename: `backend/alembic/versions/20260720_001_normalize_workflow_transition_buttons.py`
- Create: `backend/alembic/versions/20260720_002_normalize_workflow_transition_buttons.py`
- Create: `backend/alembic/versions/20260720_003_add_workflow_transition_diagram_config.py`
- Modify: `backend/app/models/workflow_definition.py`
- Modify: `backend/app/views/workflow_definition_view.py`
- Modify: `backend/app/services/workflow_definition_service.py`
- Modify: `backend/app/db/schema.py`
- Modify: `backend/tests/test_model_metadata.py`
- Modify: `backend/tests/test_workflow_definition_api.py`
- Create: `backend/tests/test_workflow_diagram_config_migration.py`

- [ ] **Step 1: Write failing metadata, migration-chain, round-trip, and validation tests**

Add metadata coverage:

```python
def test_workflow_transition_diagram_config_column_is_registered():
    column = Base.metadata.tables["workflow_transitions"].columns["diagram_config"]
    assert isinstance(column.type, JSON)
    assert column.nullable is True
```

Add an API round-trip using this exact payload:

```python
diagram_config = {
    "version": 1,
    "routing_mode": "manual",
    "source_anchor": {"side": "bottom", "ratio": 0.35},
    "target_anchor": {"side": "top", "ratio": 0.5},
    "waypoints": [{"x": 180, "y": 180}, {"x": 320, "y": 180}],
}
```

Assert PUT and subsequent GET return the same object. Parametrize invalid cases for unsupported versions/modes/sides, ratios outside `[0, 1]`, booleans/NaN-like non-numbers, more than 32 waypoints, and a diagonal segment. Add a migration test that imports revisions and asserts:

```python
assert deduplicate.revision == "20260720_001"
assert normalize.revision == "20260720_002"
assert normalize.down_revision == "20260720_001"
assert diagram.revision == "20260720_003"
assert diagram.down_revision == "20260720_002"
```

- [ ] **Step 2: Run focused backend tests and confirm RED**

Run:

```powershell
cd backend
python -m pytest tests/test_model_metadata.py tests/test_workflow_definition_api.py tests/test_workflow_diagram_config_migration.py -q
```

Expected: failures for the missing column/field and duplicate or missing migration revisions.

- [ ] **Step 3: Correct the migration chain and add the new column migration**

Rename the normalization migration and set:

```python
revision = "20260720_002"
down_revision = "20260720_001"
```

Create the next migration:

```python
revision = "20260720_003"
down_revision = "20260720_002"

def upgrade() -> None:
    op.add_column(
        "workflow_transitions",
        sa.Column("diagram_config", sa.JSON(), nullable=True, comment="diagram routing config"),
    )

def downgrade() -> None:
    op.drop_column("workflow_transitions", "diagram_config")
```

- [ ] **Step 4: Add model/view/schema support and strict validation**

Add `diagram_config` beside `ui_config` in the SQLAlchemy and Pydantic transition models. Add the schema bootstrap column after `form_config`.

Implement constants and validation in `workflow_definition_service.py`:

```python
DIAGRAM_SIDES = {"top", "right", "bottom", "left"}
DIAGRAM_ROUTING_MODES = {"manual"}
MAX_DIAGRAM_WAYPOINTS = 32

def _validate_diagram_config(
    config: dict | None,
    from_state: WorkflowStateBase,
    to_state: WorkflowStateBase,
) -> None:
    if not config:
        return
    if not isinstance(config, dict) or set(config) != {
        "version", "routing_mode", "source_anchor", "target_anchor", "waypoints"
    }:
        raise _diagram_error()
    if config["version"] != 1 or config["routing_mode"] not in DIAGRAM_ROUTING_MODES:
        raise _diagram_error()
    for anchor_name in ("source_anchor", "target_anchor"):
        anchor = config[anchor_name]
        if not isinstance(anchor, dict) or set(anchor) != {"side", "ratio"}:
            raise _diagram_error()
        ratio = anchor["ratio"]
        if anchor["side"] not in DIAGRAM_SIDES or isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not 0 <= ratio <= 1:
            raise _diagram_error()
    points = config["waypoints"]
    if not isinstance(points, list) or len(points) > MAX_DIAGRAM_WAYPOINTS:
        raise _diagram_error()
    # Resolve anchors against from_state/to_state, then validate finite x/y values
    # and every segment's orthogonality including the first and last segment.
```

Build a state-by-input-ID map in graph validation and call `_validate_diagram_config(transition.diagram_config, source_state, target_state)`. Persistence already uses `model_dump`, so the new field is then stored with the other transition fields.

- [ ] **Step 5: Run migration and backend tests**

Run:

```powershell
cd backend
python -m alembic heads
python -m alembic upgrade head
python -m pytest tests/test_model_metadata.py tests/test_workflow_definition_api.py tests/test_workflow_diagram_config_migration.py -q
```

Expected: one head, `20260720_003`; all selected tests pass.

- [ ] **Step 6: Commit backend persistence**

```powershell
git add backend/alembic/versions backend/app/models/workflow_definition.py backend/app/views/workflow_definition_view.py backend/app/services/workflow_definition_service.py backend/app/db/schema.py backend/tests/test_model_metadata.py backend/tests/test_workflow_definition_api.py backend/tests/test_workflow_diagram_config_migration.py
git commit -m "feat: persist workflow diagram routes"
```

### Task 2: Build The Manual Orthogonal Route Model

**Files:**
- Create: `frontend/src/utils/workflowManualRoute.js`
- Create: `frontend/src/utils/workflowManualRoute.test.mjs`
- Modify: `frontend/src/utils/workflowTransitionConfig.js`
- Modify: `frontend/src/utils/workflowTransitionConfig.test.mjs`

- [ ] **Step 1: Write failing pure-function tests**

Cover these public functions and contracts:

```js
import {
  anchorPointForNode,
  createManualDiagramConfig,
  manualRoutePoints,
  moveManualAnchor,
  moveManualSegment,
  normalizeManualWaypoints
} from './workflowManualRoute.js'
```

Required assertions:

```js
assert.deepEqual(anchorPointForNode(node, { side: 'bottom', ratio: 0.25 }), { x: 37.5, y: 42 })
assert.equal(moveManualAnchor(config, 'source', { x: 70, y: 41 }, node).source_anchor.side, 'bottom')
assert.deepEqual(moveManualSegment(config, 1, { x: 0, y: 160 }, from, to).waypoints, [
  { x: 118, y: 160 }, { x: 300, y: 160 }
])
assert.deepEqual(normalizeManualWaypoints([
  { x: 10, y: 10 }, { x: 10, y: 10 }, { x: 20, y: 10 }, { x: 30, y: 10 }
]), [{ x: 10, y: 10 }, { x: 30, y: 10 }])
```

Also verify that moving an endpoint preserves intermediate tracks and that output points remain finite and orthogonal.

- [ ] **Step 2: Run the focused test and confirm RED**

```powershell
cd frontend
npm test -- workflowManualRoute workflowTransitionConfig
```

Expected: module-not-found or missing-export failures.

- [ ] **Step 3: Implement the pure route module**

Use these constants and data boundaries:

```js
export const WORKFLOW_NODE_WIDTH = 118
export const WORKFLOW_NODE_HEIGHT = 42
const CORNER_GUARD = 8
const SIDES = new Set(['top', 'right', 'bottom', 'left'])
```

`anchorPointForNode` converts side/ratio to a point and clamps the rendered coordinate 8px from corners. `moveManualAnchor` picks the closest node side and stores the pointer projection as a ratio. `moveManualSegment` changes only `y` for horizontal segments or `x` for vertical segments and updates the segment's adjacent waypoint pair. `normalizeManualWaypoints` removes duplicates and redundant collinear points without introducing diagonals.

- [ ] **Step 4: Clone and serialize diagram config safely**

Update transition normalization so nested geometry is not mutated through drawer drafts:

```js
diagram_config: item.diagram_config ? structuredClone(item.diagram_config) : null,
```

Serialization keeps a non-empty manual config and emits `null` for automatic routing.

- [ ] **Step 5: Run tests and commit**

```powershell
cd frontend
npm test -- workflowManualRoute workflowTransitionConfig
cd ..
git add frontend/src/utils/workflowManualRoute.js frontend/src/utils/workflowManualRoute.test.mjs frontend/src/utils/workflowTransitionConfig.js frontend/src/utils/workflowTransitionConfig.test.mjs
git commit -m "feat: model manual workflow routes"
```

### Task 3: Project Manual Routes And Make Node Drag Final

**Files:**
- Modify: `frontend/src/utils/workflowEdgePath.js`
- Modify: `frontend/src/utils/workflowEdgePath.test.mjs`
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Modify: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`
- Modify: `frontend/src/utils/workflowDragViews.test.mjs`

- [ ] **Step 1: Write failing mixed-route and drag-contract tests**

Add an edge-path test with one automatic transition and one transition containing `diagram_config`. Assert the manual view has the exact stored track, while the automatic view still avoids obstacles. Assert both return `path`, `points`, `start`, `end`, label coordinates, and bounds.

Replace the old hybrid preview component contract with:

```js
assert.doesNotMatch(source, /combineWorkflowDragViews/)
assert.doesNotMatch(source, /buildWorkflowEdgePreviewViews/)
assert.match(source, /requestAnimationFrame/)
assert.match(source, /fullTransitionViews\.value/)
```

Add a pure contract asserting the rendered edge path immediately before and after `stopDrag()` comes from the same full projection.

- [ ] **Step 2: Run selected tests and confirm RED**

```powershell
cd frontend
npm test -- workflowEdgePath workflowDesignerAutoLayout workflowDragViews
```

Expected: manual route is ignored and the component still imports hybrid preview helpers.

- [ ] **Step 3: Add manual projection to `workflowEdgePath`**

Before automatic route classification, branch on a valid manual config:

```js
const manualPoints = manualRoutePoints(edge.from, edge.to, edge.transition.diagram_config)
if (manualPoints) {
  view = routeViewWithClearLabel(manualPoints, labelBounds, globalReservations) || routedEdgeView(manualPoints)
} else {
  view = buildAutomaticView(edge, metadata, states, globalReservations, maximumNodeBottom)
}
```

Reserve manual view labels and segments in the same global reservation structure so later automatic labels avoid them. Do not mutate `diagram_config` during projection.

- [ ] **Step 4: Replace hybrid drag preview with animation-frame full routing**

Remove `buildWorkflowEdgePreviewViews`, `combineWorkflowDragViews`, frozen `edgeViews`, and frozen `canvasEdges` from the component drag state. Add pending pointer coordinates and one scheduled frame:

```js
function onDrag(event) {
  if (!dragging.state) return
  dragging.pendingX = event.clientX
  dragging.pendingY = event.clientY
  if (dragging.frame) return
  dragging.frame = requestAnimationFrame(flushNodeDrag)
}
```

`flushNodeDrag` applies the latest clamped coordinates. `transitionViews` always returns `fullTransitionViews.value`. `stopDrag` flushes any pending coordinates, cancels the scheduled frame, and ends the drag without changing the routing source.

- [ ] **Step 5: Run tests and commit**

```powershell
cd frontend
npm test -- workflowManualRoute workflowEdgePath workflowDesignerAutoLayout workflowDragViews workflowViewport
cd ..
git add frontend/src/utils/workflowEdgePath.js frontend/src/utils/workflowEdgePath.test.mjs frontend/src/components/WorkflowDesigner.vue frontend/src/components/workflowDesignerAutoLayout.test.mjs frontend/src/utils/workflowDragViews.test.mjs
git commit -m "fix: render final workflow routes while dragging"
```

### Task 4: Add Node Badges And Direct Route Editing

**Files:**
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Modify: `frontend/src/components/WorkflowAdvancedConfigDrawer.vue`
- Modify: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`
- Modify: `frontend/src/components/workflowAdvancedConfigDrawer.test.mjs`
- Modify: `frontend/src/utils/workflowViewport.test.mjs`
- Modify: `frontend/src/utils/workflowAutoLayout.js`
- Modify: `frontend/src/utils/workflowAutoLayout.test.mjs`

- [ ] **Step 1: Write failing badge and manual-edit interaction contracts**

Require the node group to contain one badge per action-bearing node and forbid the old external trigger:

```js
assert.match(source, /class="workflow-node-action-badge"/)
assert.match(source, /:aria-label="nodeActionAriaLabel\(state\)"/)
assert.doesNotMatch(source, /class="workflow-node-action-trigger"/)
assert.doesNotMatch(source, /nodeActionTriggerBounds/)
```

Require selected-edge endpoint and segment targets:

```js
assert.match(source, /workflow-edge-endpoint/)
assert.match(source, /workflow-edge-segment-hit/)
assert.match(source, /startEndpointDrag/)
assert.match(source, /startSegmentDrag/)
assert.match(source, /cancelRouteDrag/)
```

Require a drawer `reset-diagram-route` emit and “恢复自动布线” command.

- [ ] **Step 2: Run focused tests and confirm RED**

```powershell
cd frontend
npm test -- workflowDesignerAutoLayout workflowAdvancedConfigDrawer workflowViewport workflowAutoLayout
```

- [ ] **Step 3: Move the operation entry into each node**

Render the badge after node text inside the node's SVG group when the state has same-state actions. The badge uses a stable 20px circle at the top-right, contains only the count, opens the existing menu, and is keyboard accessible. Anchor the HTML menu to the badge's actual `getBoundingClientRect()`.

Delete external trigger bounds from `workflowCanvasSize` and remove the action slot from `workflowAutoLayout`; action count must no longer change row height.

- [ ] **Step 4: Add route edit state and SVG hit targets**

Maintain one exclusive route drag snapshot:

```js
const routeDrag = reactive({
  kind: '',
  transition: null,
  endpoint: '',
  segmentIndex: -1,
  originalConfig: null
})
```

For the selected non-self transition, render two small hollow endpoint circles and transparent 12px-wide hit paths for internal segments. Segment targets use `row-resize` for horizontal segments and `col-resize` for vertical segments; no bend-point rectangles or circles are rendered.

On first edit, seed `diagram_config` from the currently rendered edge points and anchors. Pointer movement calls the pure functions from Task 2. Mouseup keeps the new config; Escape restores `originalConfig`. Route editing closes the action menu and cannot start while node/viewport dragging is active.

- [ ] **Step 5: Add drawer reset and layout reset semantics**

Add a “画布布线” row to the drawer showing 自动布线/手工布线. In manual mode show a danger-confirmed “恢复自动布线” button that emits `reset-diagram-route`. The designer handles it by setting the selected transition's `diagram_config` to `null`.

Update “整理布局” confirmation to state that manual routes will be cleared, then set every transition's `diagram_config = null` before applying auto layout. Applying a template also results in transitions without prior manual diagram config.

- [ ] **Step 6: Run tests and commit**

```powershell
cd frontend
npm test -- workflowManualRoute workflowEdgePath workflowDesignerAutoLayout workflowAdvancedConfigDrawer workflowViewport workflowAutoLayout
cd ..
git add frontend/src/components/WorkflowDesigner.vue frontend/src/components/WorkflowAdvancedConfigDrawer.vue frontend/src/components/workflowDesignerAutoLayout.test.mjs frontend/src/components/workflowAdvancedConfigDrawer.test.mjs frontend/src/utils/workflowViewport.test.mjs frontend/src/utils/workflowAutoLayout.js frontend/src/utils/workflowAutoLayout.test.mjs
git commit -m "feat: edit workflow routes on canvas"
```

### Task 5: Full Verification And Browser Acceptance

**Files:**
- Modify only files above if verification reproduces a defect.

- [ ] **Step 1: Run all backend tests**

```powershell
cd backend
python -m pytest -q
```

Expected: zero failures.

- [ ] **Step 2: Run all frontend tests and production build**

```powershell
cd frontend
npm test
npm run build
```

Expected: zero test failures and Vite exits 0; existing third-party PURE and chunk-size warnings are acceptable.

- [ ] **Step 3: Verify migrations and worktree integrity**

```powershell
cd backend
python -m alembic heads
python -m alembic current
cd ..
git diff --check
git status --short
```

Expected: a single `20260720_003` head/current revision, no whitespace errors, and the user's report modification remains uncommitted.

- [ ] **Step 4: Browser acceptance at desktop and narrow widths**

Using an authenticated local session, verify:

- node badges replace all external “操作 N” rectangles;
- badges open the correct menu and disabled actions remain editable;
- slow and fast node drags do not change route geometry on mouseup;
- endpoints drag continuously along all four node sides;
- internal horizontal/vertical segments drag without visible bend controls;
- Escape restores the route drag snapshot;
- save, reload, reset-to-auto, organize layout, and template apply have the specified persistence behavior;
- labels, nodes, menus, and route hit targets do not overlap incoherently at 1440x900 and a narrow viewport.

- [ ] **Step 5: Commit any acceptance-only fix, then stop temporary services**

If browser acceptance required a focused correction, rerun its regression test and commit only that correction. Keep the normal frontend/backend services running for user verification; stop only temporary acceptance ports and the brainstorming companion server.
