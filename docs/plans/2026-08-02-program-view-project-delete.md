# Program View Project Delete Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Align project-set tree project deletion with project-page project deletion.

**Architecture:** Load member lists for tree projects, then use the same direct and ancestor ownership rules that govern project-page actions. Add a permission-gated delete button with an Element Plus modal confirmation that delegates to the existing project deletion API.

**Tech Stack:** Vue 3, Element Plus, project API client, Node `assert` source-contract tests.

### Task 1: Cover the project-set deletion contract

**Files:**
- Create: `frontend/src/views/programViewProjectDelete.test.mjs`
- Modify: `frontend/src/views/ProgramsView.vue`

**Step 1: Write the failing source-contract test**

Require project-member loading, a `canManageProjectRow` gate around the delete
button, the existing project deletion confirmation text, and delegation to
`removeProject`.

**Step 2: Run the focused test**

Run: `npm test -- programviewprojectdelete`

Expected: FAIL because project-set project rows currently have no delete action.

**Step 3: Implement the minimal aligned action flow**

Import the project deletion and member APIs, load memberships after the tree,
add the project-page management predicates, and add the permission-gated delete
button plus confirmation wrapper.

**Step 4: Re-run the focused test**

Run: `npm test -- programviewprojectdelete`

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
