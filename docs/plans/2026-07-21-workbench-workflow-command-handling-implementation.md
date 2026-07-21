# Workbench Workflow Command Handling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make workbench edit commands open reusable requirement, task, and Bug editors, and make workflow confirmation behavior follow the approved single-confirmation rule.

**Architecture:** Keep `WorkflowActionButtons` responsible for executing workflow transitions and emitting page commands. Extract the three existing work-item edit dialogs into reusable components, then let both list views and `DashboardView` host those components. Put confirmation decisions and default text in pure helpers so they can be tested without mounting Vue.

**Tech Stack:** Vue 3 Composition API, Element Plus, Axios API modules, Node `assert` tests, Vite.

---

### Task 1: Define the workflow confirmation decision in pure helpers

**Files:**
- Modify: `frontend/src/utils/workflowRuntimeActions.js`
- Modify: `frontend/src/utils/workflowRuntimeActions.test.mjs`

**Step 1: Write the failing tests**

Add assertions covering these contracts:

```js
assert.equal(actionNeedsDialog(action(1, { confirm_required: true })), false)
assert.equal(actionNeedsConfirmation(action(1, { confirm_required: true })), true)
assert.equal(actionNeedsConfirmation(action(1, {
  confirm_required: true,
  requires_form: true,
  form_config: { fields: [{ field: 'comment', required: true }] }
})), false)
assert.equal(workflowConfirmationMessage(action(1, { action_name: '取消' })), '确认“取消”吗？')
```

Import `actionNeedsConfirmation` and `workflowConfirmationMessage` in the test.

**Step 2: Run the focused test and verify failure**

Run:

```powershell
cd frontend
npm test -- workflowRuntimeActions
```

Expected: FAIL because the new helpers do not exist and `confirm_required` still makes `actionNeedsDialog` return `true`.

**Step 3: Implement the minimal helper logic**

Change `actionNeedsDialog` so it returns `true` only for actual input dialogs:

```js
export function actionNeedsDialog(action) {
  return Boolean(
    action?.requires_form ||
      actionNeedsTargetStateSelection(action) ||
      action?.form_config?.allow_manual_owner ||
      (action?.form_config?.fields || []).length
  )
}
```

Add:

```js
export function actionNeedsConfirmation(action) {
  return Boolean(action?.confirm_required && !actionNeedsDialog(action))
}

export function workflowConfirmationMessage(action) {
  return `确认“${action?.action_name || '当前操作'}”吗？`
}
```

Do not read `ui_config.confirm_message` or `ui_config.confirm_title`; the approved behavior is system-generated text only.

**Step 4: Run the focused test and verify pass**

Run:

```powershell
cd frontend
npm test -- workflowRuntimeActions
```

Expected: PASS and print `workflowRuntimeActions tests passed`.

**Step 5: Commit**

```powershell
git add frontend/src/utils/workflowRuntimeActions.js frontend/src/utils/workflowRuntimeActions.test.mjs
git commit -m "test: define workflow confirmation behavior"
```

### Task 2: Apply the single-confirmation rule in the action component

**Files:**
- Modify: `frontend/src/components/WorkflowActionButtons.vue`
- Create: `frontend/src/components/workflowActionButtonsBehavior.test.mjs`

**Step 1: Write a failing source-contract test**

Read `WorkflowActionButtons.vue` and assert that it imports and calls `actionNeedsConfirmation` and `workflowConfirmationMessage`. Assert that `submitActiveAction` does not contain `ElMessageBox.confirm`, because form submission must not open a second confirmation.

```js
const submitBlock = source.slice(
  source.indexOf('async function submitActiveAction'),
  source.indexOf('async function submitAction')
)
assert.doesNotMatch(submitBlock, /ElMessageBox\.confirm/)
```

**Step 2: Run the focused test and verify failure**

Run:

```powershell
cd frontend
npm test -- workflowActionButtonsBehavior
```

Expected: FAIL because confirmation is still performed from `submitActiveAction`.

**Step 3: Update the component flow**

In `openAction`:

1. Keep emitting non-`add_information` page commands before transition execution.
2. Open the input dialog when `actionNeedsDialog(action)` is true.
3. Otherwise, when `actionNeedsConfirmation(action)` is true, call one system confirmation:

```js
await ElMessageBox.confirm(
  workflowConfirmationMessage(action),
  '提示',
  {
    type: buttonType(action),
    confirmButtonText: '确认',
    cancelButtonText: '取消'
  }
)
```

4. Execute the transition after confirmation.

Remove `confirmMessage` and remove all confirmation logic from `submitActiveAction`. Keep payload validation before form submission.

**Step 4: Run focused tests**

Run:

```powershell
cd frontend
npm test -- workflowRuntimeActions workflowActionButtonsBehavior
```

Expected: both test files PASS.

**Step 5: Commit**

```powershell
git add frontend/src/components/WorkflowActionButtons.vue frontend/src/components/workflowActionButtonsBehavior.test.mjs
git commit -m "fix: avoid duplicate workflow confirmations"
```

### Task 3: Extract reusable work-item edit dialogs

**Files:**
- Create: `frontend/src/components/work-items/RequirementEditDialog.vue`
- Create: `frontend/src/components/work-items/TaskEditDialog.vue`
- Create: `frontend/src/components/work-items/BugEditDialog.vue`
- Create: `frontend/src/components/workItemEditDialogs.test.mjs`
- Modify: `frontend/src/views/RequirementsView.vue`
- Modify: `frontend/src/views/TasksView.vue`
- Modify: `frontend/src/views/BugsView.vue`

**Step 1: Write a failing component-contract test**

Create a source test that requires all three files and verifies each component exposes the shared contract:

```text
props: modelValue, itemId
emits: update:modelValue, saved
open behavior: fetch the latest object detail by itemId
save behavior: call the matching update API
failure behavior: call showActionError without closing the dialog
```

Also assert that each list view imports and renders its matching edit component.

**Step 2: Run the focused test and verify failure**

Run:

```powershell
cd frontend
npm test -- workItemEditDialogs
```

Expected: FAIL because the shared dialog files do not exist.

**Step 3: Implement `RequirementEditDialog.vue`**

Move the existing requirement edit fields, priority normalization, payload construction, and `updateRequirement` call into the component. The component must:

- fetch the current record with `fetchRequirement(itemId)` whenever it opens;
- load projects, iterations, and users needed by its selects;
- hide the owner selector during edit, preserving the current list-page rule;
- validate project and title before saving;
- emit `update:modelValue=false` and `saved` only after a successful patch;
- keep the dialog open and form state intact when the patch fails.

**Step 4: Implement `TaskEditDialog.vue`**

Move the existing task edit fields and reuse `deriveTaskBranch`. Load the current task, projects, requirements, and users on open. Preserve project/requirement consistency and task-branch derivation. Emit the same shared events and keep form contents after failure.

**Step 5: Implement `BugEditDialog.vue`**

Move the existing Bug edit fields, `RichTextPasteEditor`, priority badges, nullable ID normalization, and `updateBug` call. Load the current Bug plus projects, requirements, tasks, test cases, test runs, users, and iterations required by the form. Preserve the current iteration-option rules.

**Step 6: Replace list-page edit branches**

In each list view:

- keep the existing create dialog and create submission behavior;
- change `openEdit(row)` to set `editingId` and open the shared edit component;
- render the shared component with `v-model`, `:item-id="editingId"`, and `@saved="loadData"`;
- remove duplicated edit-only patch logic after the shared component is active.

This ensures the workbench and list views execute the same edit code.

**Step 7: Run focused tests and build**

Run:

```powershell
cd frontend
npm test -- workItemEditDialogs workItemPatchPayload taskBranchRules bugIterations
npm run build
```

Expected: all selected tests PASS and Vite build completes without Vue template errors.

**Step 8: Commit**

```powershell
git add frontend/src/components/work-items frontend/src/components/workItemEditDialogs.test.mjs frontend/src/views/RequirementsView.vue frontend/src/views/TasksView.vue frontend/src/views/BugsView.vue
git commit -m "refactor: share work item edit dialogs"
```

### Task 4: Handle edit commands in the workbench

**Files:**
- Create: `frontend/src/utils/workbenchWorkflowCommands.js`
- Create: `frontend/src/utils/workbenchWorkflowCommands.test.mjs`
- Create: `frontend/src/views/workbenchWorkflowCommands.test.mjs`
- Modify: `frontend/src/views/DashboardView.vue`

**Step 1: Write failing command-resolution tests**

Test a pure resolver:

```js
assert.deepEqual(
  resolveWorkbenchWorkflowCommand({ object_type: 'requirement', id: 3919 }, 'edit'),
  { kind: 'edit', objectType: 'requirement', objectId: 3919 }
)
assert.equal(resolveWorkbenchWorkflowCommand({ object_type: 'test_case', id: 7 }, 'edit'), null)
assert.equal(resolveWorkbenchWorkflowCommand({ object_type: 'task', id: 8 }, 'unknown'), null)
```

The supported edit types are exactly `requirement`, `task`, and `bug`.

**Step 2: Write a failing Dashboard integration contract**

Read `DashboardView.vue` and assert that:

- `WorkflowActionButtons` has `@command="handleWorkflowCommand(row, $event)"`;
- all three edit dialog components are imported;
- the handler delegates to `resolveWorkbenchWorkflowCommand`;
- successful saves call `loadWorkbench`.

**Step 3: Run focused tests and verify failure**

Run:

```powershell
cd frontend
npm test -- workbenchWorkflowCommands
```

Expected: FAIL because the resolver and Dashboard listener do not exist.

**Step 4: Implement the resolver**

Add a small pure function that validates `commandType`, object type, and numeric object ID, returning an edit descriptor or `null`. Do not route based on action names.

**Step 5: Wire `DashboardView.vue`**

Add state for the active editor type and object ID. Listen to `@command` on `WorkflowActionButtons`, resolve the command, and open exactly one matching shared editor. Render the three editor components with type guards, and use a single `handleEditorSaved` function that closes the active editor and awaits `loadWorkbench()`.

Unknown command types must do nothing and must not call the workflow execution API.

**Step 6: Run focused tests and build**

Run:

```powershell
cd frontend
npm test -- workbenchWorkflowCommands workItemEditDialogs workflowRuntimeActions workflowActionButtonsBehavior
npm run build
```

Expected: all selected tests PASS and the production build succeeds.

**Step 7: Commit**

```powershell
git add frontend/src/utils/workbenchWorkflowCommands.js frontend/src/utils/workbenchWorkflowCommands.test.mjs frontend/src/views/workbenchWorkflowCommands.test.mjs frontend/src/views/DashboardView.vue
git commit -m "fix: handle workbench edit commands"
```

### Task 5: Full regression and browser verification

**Files:**
- Modify only if a verified defect is found in the files from Tasks 1-4.

**Step 1: Run the full frontend test suite**

Run:

```powershell
cd frontend
npm test
```

Expected: all test files PASS.

**Step 2: Run the production build**

Run:

```powershell
cd frontend
npm run build
```

Expected: Vite build exits with code 0.

**Step 3: Verify workbench editing in the browser**

Using `http://127.0.0.1:5173` with a project-member account:

1. Open workbench “未分派”.
2. Open “更多” and click requirement “编辑”.
3. Verify the requirement editor opens and contains the latest server values.
4. Save a harmless title/description change and verify the workbench refreshes.
5. Repeat the open-and-cancel check for one task and one Bug.

Expected: all three editors open; successful saves refresh the row; cancel makes no request.

**Step 4: Verify confirmation behavior in the browser**

Check three configured transitions:

1. no form + confirmation enabled: one confirmation dialog with `确认“{流转名称}”吗？`;
2. no form + confirmation disabled: executes without a confirmation dialog;
3. form + confirmation enabled: opens the form and executes after submit without a second dialog.

Expected: exactly the approved number of dialogs in each case.

**Step 5: Review the final diff**

Run:

```powershell
git status --short
git diff --check
```

Expected: no whitespace errors; the pre-existing user change in `docs/reports/2026-07-17-workflow-id-finalization-report.md` remains untouched.

**Step 6: Commit any verification-only correction**

Only when Step 3 or Step 4 exposed a defect, commit the smallest correction with its regression test. Otherwise, do not create an empty commit.
