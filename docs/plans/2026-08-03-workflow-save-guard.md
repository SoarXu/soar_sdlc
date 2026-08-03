# Workflow Save Guard Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Prevent the workflow save action from opening an unsaved-changes dialog or issuing concurrent duplicate saves.

**Architecture:** Keep one module-local Promise for the active graph save. `saveGraph` returns that Promise when already saving. The discard guard returns `false` while saving so route or parent navigation stays put without opening a dialog; the dialog's save action calls the same single-flight save function.

**Tech Stack:** Vue 3, JavaScript, Node source-contract tests.

### Task 1: Specify saving and guard behavior

**Files:**
- Modify: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`
- Test: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`

**Step 1: Write the failing test**

Add assertions that the designer declares an in-flight save Promise, `saveGraph` returns it when present, and `confirmDiscardWorkflowChanges` returns `false` before opening a dialog while a save is active.

**Step 2: Run test to verify it fails**

Run: `npm test -- workflowdesignerautolayout`

Expected: FAIL because saving has no shared Promise and the discard guard does not check it.

### Task 2: Serialize workflow saves

**Files:**
- Modify: `frontend/src/components/WorkflowDesigner.vue:572-612`
- Test: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`

**Step 1: Write minimal implementation**

Add `saveGraphInFlight`. Wrap the existing save logic in one Promise, return it to every caller, and clear the shared reference only after completion. Preserve existing validation and success feedback.

**Step 2: Run test to verify it passes**

Run: `npm test -- workflowdesignerautolayout`

Expected: PASS.

### Task 3: Keep the discard dialog for genuine unsaved exits

**Files:**
- Modify: `frontend/src/components/WorkflowDesigner.vue:747-789`
- Modify: `frontend/src/components/workflowDesignerDrawerIntegration.test.mjs`
- Test: `frontend/src/components/workflowDesignerDrawerIntegration.test.mjs`

**Step 1: Write the failing test**

Assert that `saveWorkflowAndContinue` calls the shared `saveGraph` without creating an independent save path, and that discard confirmation only opens when no save is active and changes remain.

**Step 2: Write minimal implementation**

Keep the current dialog resolver behavior. Let it await `saveGraph`; when the same save succeeds, close and continue; when it fails, restore dialog interaction.

**Step 3: Run test to verify it passes**

Run: `npm test -- workflowdesignerdrawerintegration workflowdesignerautolayout`

Expected: PASS.

### Task 4: Verify the frontend

**Files:**
- Verify only.

**Step 1: Run full tests and build**

Run: `npm test`

Run: `npm run build`

**Step 2: Inspect whitespace**

Run: `git diff --check`
