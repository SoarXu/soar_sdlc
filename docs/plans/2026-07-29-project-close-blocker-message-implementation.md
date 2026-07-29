# Project Close Blocker Message Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the nested modal shown for an unfinished project iteration with an automatically dismissed Chinese warning message.

**Architecture:** `ProjectsView.vue` will recognize the existing close API's iteration blocker detail before invoking the shared modal error helper. The specialized branch uses Element Plus `ElMessage.warning`; all unrelated failures retain their existing behavior.

**Tech Stack:** Vue 3 script setup, Element Plus, Node source-contract tests, Vite.

---

### Task 1: Specify the close-blocker UI contract

**Files:**
- Create: `frontend/src/views/projectsViewCloseBlockerMessage.test.mjs`
- Modify: `frontend/src/views/ProjectsView.vue: imports and changeProjectStatus`

**Step 1: Write the failing test**

Create a Node assertion test that reads `ProjectsView.vue`, extracts the project-status failure branch, and requires all of the following:

```js
assert.match(projectStatusFailure, /isUnfinishedIterationBlocker\(error\)/)
assert.match(projectStatusFailure, /ElMessage\.warning\('项目存在未结束迭代，无法关闭。'\)/)
assert.doesNotMatch(iterationBlockerBranch, /showActionError/)
```

**Step 2: Run test to verify it fails**

Run: `npm test -- projectsViewCloseBlockerMessage`

Expected: FAIL because `ProjectsView.vue` currently routes every status error through `showActionError`.

**Step 3: Write minimal implementation**

Import `ElMessage`, add a narrowly scoped helper that recognizes the API detail containing `unfinished iteration`, and branch in `changeProjectStatus` to call the Chinese warning. Keep `showActionError` for all other errors, then rethrow as today so the dialog remains open.

**Step 4: Run test to verify it passes**

Run: `npm test -- projectsViewCloseBlockerMessage`

Expected: PASS with the close-blocker feedback contract printed.

### Task 2: Verify the frontend change

**Files:**
- Test: `frontend/src/views/projectsViewCloseBlockerMessage.test.mjs`

**Step 1: Run the frontend suite**

Run: `npm test`

Expected: all frontend source-contract tests pass.

**Step 2: Run the production build**

Run: `npm run build`

Expected: Vite completes successfully.

**Step 3: Review the focused diff**

Run: `git diff --check && git diff -- frontend/src/views/ProjectsView.vue frontend/src/views/projectsViewCloseBlockerMessage.test.mjs`

Expected: no whitespace errors; only the specialized close-blocker behavior and its test change.
