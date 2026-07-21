# Workflow ELK Layout And Routing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the custom organize-layout result with deterministic ELK layered layout, persist generated orthogonal routes, and warn before discarding any unsaved graph changes.

**Architecture:** A lazy ELK adapter maps the existing workflow graph to ELK JSON and converts one successful result into new state coordinates plus versioned `generated` diagram routes. Rendering continues through the existing SVG edge-view contract; manual routes override generated routes, while atomic drag frames regenerate non-manual geometry. A normalized graph snapshot provides explicit-save dirty tracking.

**Tech Stack:** Vue 3 Composition API, elkjs Web Worker, JavaScript ES modules, Node assert tests, FastAPI, Pydantic, pytest, Vite

---

### Task 1: Accept Generated Diagram Routes

**Files:**
- Modify: `backend/app/services/workflow_definition_service.py`
- Modify: `backend/tests/test_workflow_definition_api.py`
- Modify: `frontend/src/utils/workflowManualRoute.js`
- Modify: `frontend/src/utils/workflowManualRoute.test.mjs`
- Modify: `frontend/src/components/WorkflowAdvancedConfigDrawer.vue`
- Modify: `frontend/src/components/workflowAdvancedConfigDrawer.test.mjs`

**Step 1: Write failing backend and frontend tests**

Add an API round trip for a valid `routing_mode: "generated"` config and retain rejection of unknown modes. Add frontend tests that render generated points through the same geometry function, report generated as automatic, and expose reset only for manual routes.

**Step 2: Verify RED**

Run:

```powershell
cd backend
python -m pytest tests/test_workflow_definition_api.py -q
cd ../frontend
npm test -- workflowManualRoute workflowAdvancedConfigDrawer
```

Expected: generated mode is rejected or ignored.

**Step 3: Implement minimal generated-mode support**

Allow `{"manual", "generated"}` in backend validation. Rename the frontend point reader to accept either stored geometry mode while keeping edit functions manual. Add helpers `isManualDiagramRoute` and `isGeneratedDiagramRoute`; use them in the drawer.

**Step 4: Verify GREEN and commit**

Run the same commands, then commit:

```powershell
git add backend/app/services/workflow_definition_service.py backend/tests/test_workflow_definition_api.py frontend/src/utils/workflowManualRoute.js frontend/src/utils/workflowManualRoute.test.mjs frontend/src/components/WorkflowAdvancedConfigDrawer.vue frontend/src/components/workflowAdvancedConfigDrawer.test.mjs
git commit -m "feat: support generated workflow routes"
```

### Task 2: Build The ELK Adapter

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Create: `frontend/src/utils/workflowElkLayout.js`
- Create: `frontend/src/utils/workflowElkLayout.test.mjs`
- Create: `frontend/src/workers/workflowElk.worker.js`
- Create or modify: `THIRD_PARTY_NOTICES.md`

**Step 1: Install the pinned dependency**

Run:

```powershell
cd frontend
npm install elkjs@0.12.0
```

Record the EPL-2.0/GPL dual-license package in `THIRD_PARTY_NOTICES.md`.

**Step 2: Write failing adapter tests**

Cover graph conversion and result conversion with a screenshot-like cyclic workflow. Assert fixed node sizes, unique ports and labels, exact layout options, exclusion of self transitions, disabled-state separation, no input mutation, normalized orthogonal generated paths, deterministic output, and per-edge fallback when geometry exceeds 32 waypoints.

**Step 3: Verify RED**

Run: `cd frontend; npm test -- workflowElkLayout`

Expected: module-not-found or missing-export failures.

**Step 4: Implement the adapter**

Export:

```js
createWorkflowElkGraph(states, transitions, initialStateId)
convertWorkflowElkResult(result, states, transitions)
layoutWorkflowWithElk(states, transitions, initialStateId, options)
```

Use stable typed IDs for nodes, edges, and ports. Parse each simple edge section from `startPoint`, `bendPoints`, and `endPoint`; convert absolute points to anchors plus waypoints. Place inactive states below the ELK active graph.

Use a lazily created Worker and a request ID. Reject on timeout, worker error, invalid output, or stale result.

**Step 5: Verify, build, and commit**

Run:

```powershell
cd frontend
npm test -- workflowElkLayout workflowManualRoute workflowEdgePath
npm run build
```

Commit the dependency, adapter, worker, tests, and notice.

### Task 3: Integrate ELK With Organize And Templates

**Files:**
- Modify: `frontend/src/utils/workflowLayoutInteraction.js`
- Modify: `frontend/src/utils/workflowLayoutInteraction.test.mjs`
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Modify: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`

**Step 1: Write failing interaction tests**

Require organization to await an injected async layout function, return both `states` and `transitions`, avoid mutating inputs, and leave the graph untouched after rejection. Require template application to await ELK before publishing the graph.

**Step 2: Verify RED**

Run: `cd frontend; npm test -- workflowLayoutInteraction workflowDesignerAutoLayout workflowElkLayout`

**Step 3: Implement transactional ELK application**

Replace `layoutWorkflowNodes` in the organization request with `layoutWorkflowWithElk`. Apply result states and transitions only after success. Keep `loading` active, show a focused error message, and leave current graph unchanged on failure. Make template organization follow the same path.

**Step 4: Verify and commit**

Run selected tests and `npm run build`, then commit with `feat: organize workflows with elk`.

### Task 4: Regenerate Generated Routes After Node Drag

**Files:**
- Modify: `frontend/src/utils/workflowDragFrame.js`
- Modify: `frontend/src/utils/workflowDragFrame.test.mjs`
- Modify: `frontend/src/utils/workflowManualRoute.js`
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Modify: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`

**Step 1: Write failing drag persistence tests**

Start with generated, manual, and route-less transitions. Assert the drag frame ignores old generated geometry, retains manual geometry, renders all coordinates atomically, and converts the final non-manual edge views into generated configs without changing manual configs.

**Step 2: Verify RED**

Run: `cd frontend; npm test -- workflowDragFrame workflowManualRoute workflowDesignerAutoLayout`

**Step 3: Implement final-frame serialization**

Add `generatedDiagramConfigFromView(view, from, to)` and a helper that applies final edge views to non-manual transitions. Use route-stripped transition clones while building drag frames. On mouseup commit node coordinates and generated configs from the same final frame before clearing it.

**Step 4: Verify and commit**

Run focused tests, all edge-path tests, and commit with `fix: persist final workflow drag routes`.

### Task 5: Track Unsaved Workflow Graph Changes

**Files:**
- Create: `frontend/src/utils/workflowGraphSnapshot.js`
- Create: `frontend/src/utils/workflowGraphSnapshot.test.mjs`
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Modify: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`

**Step 1: Write failing snapshot tests**

Normalize the definition ID, object type, initial state, state geometry, transition order, and nested diagram config into a deterministic string. Assert that every graph edit changes the snapshot while harmless object-key order changes do not.

**Step 2: Verify RED**

Run: `cd frontend; npm test -- workflowGraphSnapshot workflowDesignerAutoLayout`

**Step 3: Implement dirty tracking**

Capture the saved snapshot after load and successful save. Add `hasUnsavedGraphChanges`. Combine it with drawer draft checks in route leave, object-type switch, graph reload, template confirmation, and `beforeunload`. Use one confirmation dialog for graph changes and drawer drafts.

**Step 4: Verify and commit**

Run focused tests and commit with `feat: warn before discarding workflow edits`.

### Task 6: Full Verification And Browser Acceptance

**Files:**
- Modify only files above if verification reproduces a defect.

**Step 1: Run backend tests**

Run: `cd backend; python -m pytest -q`

**Step 2: Run frontend tests and build**

Run: `cd frontend; npm test; npm run build`

**Step 3: Verify integrity**

Run: `git diff --check; git status --short`

**Step 4: Browser acceptance**

On the screenshot-like cyclic workflow verify: no overlaps, fewer crossings, separated ports, orthogonal node-avoiding paths, deterministic repeated organization, transactional failure behavior, saved refresh stability, unsaved exit recovery, manual route preservation, and atomic real-time node dragging.

**Step 5: Commit acceptance-only corrections**

Rerun the focused regression and full frontend suite before any correction commit.
