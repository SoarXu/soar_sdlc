# Project Delete Confirmation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the project-row inline delete confirmation with the centered project-set confirmation pattern.

**Architecture:** Reuse Element Plus `ElMessageBox.confirm` and the existing `removeProject` implementation. The only template change replaces the `el-popconfirm` wrapper with a button handler; the deletion request and warning copy remain unchanged.

**Tech Stack:** Vue 3, Element Plus, Node `assert` source-contract tests.

### Task 1: Cover the confirmation contract

**Files:**
- Create: `frontend/src/views/projectDeleteConfirmation.test.mjs`
- Modify: `frontend/src/views/ProjectsView.vue`

**Step 1: Write the failing test**

Require the delete button to call `confirmRemoveProject(row.id)`, require the
exact existing warning text in `ElMessageBox.confirm`, and require confirmation
to delegate to `removeProject(id)`.

**Step 2: Run the focused test**

Run: `npm test -- projectdeleteconfirmation`

Expected: FAIL because the page currently contains `el-popconfirm`.

**Step 3: Implement the minimal confirmation wrapper**

Replace the template wrapper and add `confirmRemoveProject` using the project-set
confirmation pattern. Do not change `removeProject` or the deletion message.

**Step 4: Re-run the focused test**

Run: `npm test -- projectdeleteconfirmation`

Expected: exit code 0.

### Task 2: Verify regression safety

**Files:**
- Modify: no additional files expected

**Step 1: Run full frontend tests**

Run: `npm test`

Expected: exit code 0.

**Step 2: Build the frontend**

Run: `npm run build`

Expected: Vite exits with code 0.

**Step 3: Commit**

Do not commit automatically. Request the required delivery confirmation after
reporting verified local changes.
