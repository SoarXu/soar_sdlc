# Workflow Designer Enabled Definition Selection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the workflow designer load the enabled workflow definition for a scheme so the default Bug workflow displays definition `#33` rather than a disabled higher-ID definition.

**Architecture:** Keep the workflow-definition API response unchanged because administrative views may need historical disabled definitions. In `WorkflowDesigner.vue`, select the enabled response item before fetching its graph. Preserve the existing create-on-empty behavior, but apply it when no enabled definition exists.

**Tech Stack:** Vue 3, Element Plus, Node.js source-contract tests.

---

### Task 1: Select only enabled workflow definitions

**Files:**
- Modify: `frontend/src/components/WorkflowDesigner.vue:440-463`
- Test: `frontend/src/components/workflowDesignerAutoLayout.test.mjs`

**Step 1: Write the failing test**

Add a behavior-level test for a pure definition-selection helper. It must select
the enabled definition when a higher-ID disabled definition appears first.

```js
const selected = selectEnabledWorkflowDefinition([
  { id: 466, enabled: false },
  { id: 33, enabled: true }
])

assert.equal(selected.id, 33)
```

**Step 2: Run test to verify it fails**

Run: `npm test -- workflowDesignerAutoLayout.test.mjs`

Expected: FAIL because `selectEnabledWorkflowDefinition` does not yet exist.

**Step 3: Write minimal implementation**

Add a small helper and replace the first-item selection with it.

```js
export function selectEnabledWorkflowDefinition(definitions) {
  return definitions.find((item) => item.enabled)
}

// WorkflowDesigner.vue
let current = selectEnabledWorkflowDefinition(list.data)
if (!current) {
  // Existing definition creation flow.
}
```

**Step 4: Run test to verify it passes**

Run: `npm test -- workflowDesignerAutoLayout.test.mjs`

Expected: PASS.

**Step 5: Run the frontend suite**

Run: `npm test`

Expected: PASS with no test failures.

**Step 6: Commit**

```bash
git add frontend/src/components/WorkflowDesigner.vue frontend/src/components/workflowDesignerAutoLayout.test.mjs frontend/src/utils/workflowDefinitionSelection.js docs/plans/2026-07-29-workflow-designer-enabled-definition-selection-implementation.md
git commit -m "fix: load enabled workflow definition in designer"
```
