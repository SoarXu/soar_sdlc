# 项目操作按钮去重 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 移除项目列表行中重复的“新增项目”按钮。

**Architecture:** 保留 `WorkflowActionButtons` 的后置插槽，其中包含编辑和唯一的新增项目操作；删除插槽外重复的新增项目节点。权限判断和事件处理函数不变。

**Tech Stack:** Vue 3, Element Plus, Node.js test runner, Vite.

---

### Task 1: 锁定操作区唯一性

**Files:**
- Create: `frontend/src/views/projectsViewActionDeduplication.test.mjs`
- Modify: `frontend/src/views/ProjectsView.vue:60-66`

**Step 1: 写入失败测试**

读取 `ProjectsView.vue`，提取 `WorkflowActionButtons` 的 `after-primary` 插槽，断言其中恰有一个“新增项目”按钮，并断言该组件之后到删除确认组件之前没有第二个新增按钮。

**Step 2: 验证测试失败**

Run: `node src/views/projectsViewActionDeduplication.test.mjs`

Expected: 失败并指出存在重复的“新增项目”节点。

**Step 3: 最小修复**

删除 `WorkflowActionButtons` 之后、删除确认之前的重复 `el-button`，不改动插槽中的编辑和新增操作。

**Step 4: 验证测试通过**

Run: `node src/views/projectsViewActionDeduplication.test.mjs`

Expected: 输出唯一性断言通过。

### Task 2: 回归验证

**Files:**
- Verify: `frontend/src/views/ProjectsView.vue`
- Verify: `frontend/src/views/projectsViewActionDeduplication.test.mjs`

**Step 1:** 运行 `npm test`。

**Step 2:** 运行 `npm run build`。

**Step 3:** 运行 `git diff --check` 并保留验证输出，待主上确认交付方式后再进行 Git 操作。
