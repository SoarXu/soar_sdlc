# Iteration Detail Back To Project Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a context-aware button that returns from iteration detail to the source project's iteration tab.

**Architecture:** Reuse the `from` and `projectId` query parameters already emitted by `ProjectDetailView.vue`. Derive visibility and the destination inside `IterationDetailView.vue` without adding global state or changing routes.

**Tech Stack:** Vue 3, Vue Router, Node source-contract tests, Vite.

---

### Task 1: Add Context-Aware Project Return

**Files:**
- Modify: `frontend/src/views/IterationDetailView.vue`
- Create: `frontend/src/views/iterationDetailBackToProject.test.mjs`

**Step 1: Write the failing test**

Assert that the detail view derives a valid source project ID from `route.query`, conditionally renders “回到项目”, and routes to `project-detail` with `tab: 'iterations'`.

**Step 2: Verify RED**

Run: `npm test -- iterationDetailBackToProject`

Expected: FAIL because the context-aware button and navigation function do not exist.

**Step 3: Implement the minimal change**

Add a computed `sourceProjectId`, render the button beside “返回迭代列表”, and add `backToSourceProject()` using the existing router instance.

**Step 4: Verify GREEN**

Run: `npm test -- iterationDetailBackToProject`

Expected: PASS.

**Step 5: Run regression verification**

Run `npm test` and `npm run build`.

No commit, push, PR, or merge is performed because the user selected local-only delivery.
