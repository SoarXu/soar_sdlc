# Workflow Template Layout Preservation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Preserve template node positions and transition routing when a workflow scheme is created from or updated with a template.

**Architecture:** Workflow definitions already persist state `x/y` coordinates and transition `diagram_config`, and scheme creation already clones them. The workflow editor must apply the template preview graph directly instead of running ELK automatically, which overwrites these persisted layout fields. Manual layout remains the sole operation that invokes ELK.

**Tech Stack:** Vue 3, JavaScript, Node.js source-contract tests.

---

### Task 1: Preserve Template Graph Layout in the Designer

**Files:**
- Modify: `frontend/src/components/WorkflowDesigner.vue:533-564`
- Test: `frontend/src/components/workflowDesignerAutoLayout.test.mjs:245-253`

**Step 1: Write the failing test**

Assert that `applyTemplate` applies `graph.data` directly and does not call `layoutWorkflowWithElk`.

**Step 2: Run test to verify it fails**

Run: `npm test -- workflowDesignerAutoLayout`

Expected: failure because template application currently runs ELK and replaces graph coordinates.

**Step 3: Write minimal implementation**

Replace the automatic layout block in `applyTemplate` with `applyGraph(graph.data)`. Retain `replaceExistingTransitionsOnSave` so saving continues to replace the existing graph.

**Step 4: Run focused and full tests**

Run: `npm test -- workflowDesignerAutoLayout` and `npm test`

Expected: both commands pass.

**Step 5: Build the frontend**

Run: `npm run build`

Expected: production build succeeds.

**Step 6: Commit**

Deferred: workspace instructions require explicit delivery confirmation before Git operations.
