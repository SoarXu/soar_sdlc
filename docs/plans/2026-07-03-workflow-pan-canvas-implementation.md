# Workflow Pan Canvas Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the visual workflow designer canvas pannable so complex workflows can be spread out without crowding.

**Architecture:** Keep persisted node coordinates in the same graph data model. Add a large logical canvas and a viewport transform in the Vue component, with pure utility helpers for pan clamping and fit-to-content math.

**Tech Stack:** Vue 3, SVG, Element Plus, Vite, Node-based utility tests.

---

### Task 1: Canvas Viewport Utilities

**Files:**
- Create: `frontend/src/utils/workflowViewport.js`
- Create: `frontend/src/utils/workflowViewport.test.mjs`

**Steps:**
1. Write failing tests for clamping pan offsets, drag-to-pan deltas, and fit-to-content viewport calculation.
2. Implement pure utility functions with no DOM dependency.
3. Run `node frontend\src\utils\workflowViewport.test.mjs`.

### Task 2: WorkflowDesigner Pan Integration

**Files:**
- Modify: `frontend/src/components/WorkflowDesigner.vue`

**Steps:**
1. Increase logical canvas size.
2. Wrap SVG graph content in a translated viewport group.
3. Add background panning on blank-canvas mouse down.
4. Keep node dragging separate from canvas panning.
5. Add toolbar actions for "适应视图" and "回到原点".
6. Update CSS cursor and grid background offset.

### Task 3: Verification

**Commands:**
- `node frontend\src\utils\workflowViewport.test.mjs`
- `node frontend\src\utils\workflowEdgePath.test.mjs`
- `npm run build`

