# 项目迭代列表隐藏 ID Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Hide the technical iteration ID column from the project detail iteration list.

**Architecture:** This is a template-only change in the project detail view. API contracts and route IDs remain unchanged, while the existing structural test protects the visible table layout.

**Tech Stack:** Vue 3, Element Plus, Node assert tests, Vite.

---

### Task 1: Capture the visible-table regression

**Files:**
- Modify: `frontend/src/views/projectDetailWorkflowIterationLayout.test.mjs`

**Step 1: Write the failing test**

Add an assertion against the extracted iterations template:

```js
assert.doesNotMatch(iterationsTemplate, /<el-table-column prop="id" label="ID"/)
```

**Step 2: Run the test to verify it fails**

Run: `npm test -- projectDetailWorkflowIterationLayout`

Expected: FAIL because the ID table column is still rendered.

### Task 2: Remove the technical column

**Files:**
- Modify: `frontend/src/views/ProjectDetailView.vue`

**Step 1: Remove the ID column**

Delete the iteration table column:

```vue
<el-table-column prop="id" label="ID" width="80" />
```

**Step 2: Run the focused test**

Run: `npm test -- projectDetailWorkflowIterationLayout`

Expected: PASS.

### Task 3: Verify the frontend

**Files:**
- Verify: `frontend/src/views/projectDetailWorkflowIterationLayout.test.mjs`
- Verify: `frontend/package.json`

**Step 1: Run the frontend test suite**

Run: `npm test`

Expected: PASS.

**Step 2: Build frontend production assets**

Run: `npm run build`

Expected: exits with code 0.
