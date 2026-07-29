# Workflow Unsaved Save Actions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add direct save actions to workflow and advanced-configuration unsaved-change confirmations.

**Architecture:** Replace the two-action Element Plus message boxes with component-owned dialogs that retain a resolver for the pending action. The drawer applies its draft before resolving the close/back action. The designer saves the graph, then resolves the deferred action only after persistence succeeds.

**Tech Stack:** Vue 3 Composition API, Element Plus, Node.js source-contract tests.

---

### Task 1: Cover Direct Save Actions

**Files:**
- Modify: frontend/src/components/workflowAdvancedConfigDrawer.test.mjs
- Modify: frontend/src/components/workflowDesignerAutoLayout.test.mjs

**Step 1: Write the failing tests**

Require the drawer actions 应用并关闭, 放弃修改, and 取消. Require the
designer actions 保存流程图并继续, 放弃修改, and 取消, plus the
save-and-resume handler.

**Step 2: Run tests to verify they fail**

Run: npm test -- workflowAdvancedConfigDrawer workflowDesignerAutoLayout

Expected: FAIL because neither component owns the three-action confirmation.

### Task 2: Add Drawer Apply-And-Close Confirmation

**Files:**
- Modify: frontend/src/components/WorkflowAdvancedConfigDrawer.vue
- Test: frontend/src/components/workflowAdvancedConfigDrawer.test.mjs

**Step 1: Implement the minimum dialog state**

Store a promise resolver when a close or back action encounters a dirty draft.
Resolve it after cancellation, discard, or successful draft application.

**Step 2: Implement dialog actions**

Use a component dialog with Cancel, Discard changes, and Apply and close. On
validation failure, close only the confirmation so the drawer remains editable.

**Step 3: Run the focused test**

Run: npm test -- workflowAdvancedConfigDrawer

Expected: PASS.

### Task 3: Add Workflow Save-And-Continue Confirmation

**Files:**
- Modify: frontend/src/components/WorkflowDesigner.vue
- Test: frontend/src/components/workflowDesignerAutoLayout.test.mjs

**Step 1: Implement the minimum dialog state**

Store the title, message, and resolver used by existing leave, reload, object
type, and template confirmation paths.

**Step 2: Implement save and resume**

Make saveGraph return success status. The dialog applies pending advanced
configuration through that save path, persists the graph, then resumes the
original action only after success.

**Step 3: Run focused tests**

Run: npm test -- workflowAdvancedConfigDrawer workflowDesignerAutoLayout

Expected: PASS.

### Task 4: Regression Verification

**Files:**
- Verify: frontend/src/components/WorkflowAdvancedConfigDrawer.vue
- Verify: frontend/src/components/WorkflowDesigner.vue

**Step 1: Run all tests**

Run: npm test

Expected: PASS.

**Step 2: Build**

Run: npm run build

Expected: successful production build.
