# Workflow Disabled Transition Canvas Regression Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep transitions connected to disabled workflow states visible on the canvas while preserving their disabled, non-runnable state.

**Architecture:** The state-availability helper and graph-save service already preserve disabled transitions and use `enabled=false` to represent their availability. The canvas projection must pass every transition with valid endpoint states to the edge renderer; the renderer's existing `disabled` class supplies the grey dashed presentation. Layout may continue to exclude disabled states from its active graph because this change only restores rendering, not layout participation.

**Tech Stack:** Vue 3, JavaScript ES modules, Node assertion tests, Vite.

---

### Task 1: Lock the canvas projection contract with a regression test

**Files:**
- Modify: `frontend/src/utils/workflowCanvasProjection.test.mjs`
- Verify: `frontend/src/utils/workflowCanvasProjection.js`

**Step 1: Write the failing test**

Change the existing disabled-state transition assertion so a valid transition from disabled state `3` to enabled state `1` is included in `routedTransitions`:

```javascript
assert.deepEqual(result.routedTransitions.map((item) => item.id), [11, 15])
```

**Step 2: Run the focused test to verify RED**

Run:

```powershell
Set-Location frontend
node src/utils/workflowCanvasProjection.test.mjs
```

Expected: fail because `projectWorkflowCanvas()` rejects transitions when either endpoint state is disabled.

### Task 2: Preserve valid disabled transitions in the canvas projection

**Files:**
- Modify: `frontend/src/utils/workflowCanvasProjection.js`
- Test: `frontend/src/utils/workflowCanvasProjection.test.mjs`

**Step 1: Implement the minimum production change**

Build `routedTransitions` from all transitions whose two endpoint IDs exist and differ. Do not test endpoint `enabled` values here. Continue filtering malformed endpoint references and continue treating self-transitions as state actions.

**Step 2: Run the focused test to verify GREEN**

Run:

```powershell
Set-Location frontend
node src/utils/workflowCanvasProjection.test.mjs
```

Expected: exit code 0 and `workflow canvas projection tests passed`.

### Task 3: Verify integration and production build

**Files:**
- Verify: `frontend/src/components/WorkflowDesigner.vue`
- Verify: `frontend/src/utils/workflowStateAvailability.test.mjs`
- Verify: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`

**Step 1: Run focused workflow tests**

```powershell
Set-Location frontend
node src/utils/workflowStateAvailability.test.mjs
node src/utils/workflowCanvasProjection.test.mjs
node src/components/workflowDesignerAutoLayout.test.mjs
```

Expected: all commands exit code 0. The first proves state disablement persists; the second proves the disabled edge remains renderable; the third proves the designer still consumes the shared projection.

**Step 2: Build the frontend**

```powershell
Set-Location frontend
npm run build
```

Expected: Vite build exits code 0.

**Step 3: Inspect the final diff**

```powershell
Set-Location ..
git diff --check
git status --short
```

Expected: whitespace check succeeds and only the N-001 correction plus pre-existing local files are present.

### Task 4: Correct the issue record

**Files:**
- Modify: `docs/issues/2026-08-22-后续问题清单.md`

**Step 1: Mark the reopened issue**

Change N-001 to `实施中` before implementation. Add an addendum recording that the canvas projection excluded valid transitions attached to disabled states, contrary to the visual-retention rule.

**Step 2: Record verification evidence after all checks pass**

Set the issue to `已解决` only after Task 3 completes with fresh evidence, retaining the regression cause and test results.
