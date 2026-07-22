# 项目集与项目状态动作排序 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在项目集树和独立项目列表中，将生命周期状态动作稳定地显示在编辑操作之前。

**Architecture:** 只调整 Vue 模板中按钮与 `WorkflowActionButtons` 组件的顺序，不改变状态转换数据、权限逻辑或接口调用。通过读取模板文本的轻量测试验证每个节点的相对顺序。

**Tech Stack:** Vue 3、Element Plus、Node.js 测试脚本。

---

### Task 1: 覆盖操作顺序

**Files:**
- Create: `frontend/src/views/programActionOrder.test.mjs`
- Test: `frontend/src/views/programActionOrder.test.mjs`

**Step 1: Write the failing test**

断言 `ProgramsView.vue` 中项目集节点的启动按钮位于编辑按钮之前，项目节点的 `WorkflowActionButtons` 位于编辑按钮之前；同时断言 `ProjectsView.vue` 保持该顺序。

**Step 2: Run test to verify it fails**

Run: `node frontend/src/views/programActionOrder.test.mjs`

Expected: FAIL，因为当前项目集和项目树节点的编辑按钮在状态动作前。

**Step 3: Write minimal implementation**

在 `ProgramsView.vue` 中把项目集的条件状态按钮块移动到编辑按钮之前，并把项目节点的 `WorkflowActionButtons` 移动到编辑按钮之前。

**Step 4: Run test to verify it passes**

Run: `node frontend/src/views/programActionOrder.test.mjs`

Expected: PASS。

### Task 2: 回归验证

**Files:**
- Modify: `frontend/src/views/ProgramsView.vue`
- Test: `frontend/src/views/programActionOrder.test.mjs`

**Step 1: Run the frontend test suite**

Run: `npm test`

Working directory: `frontend`

Expected: all tests pass.

**Step 2: Build the frontend**

Run: `npm run build`

Working directory: `frontend`

Expected: Vite build completes successfully.
