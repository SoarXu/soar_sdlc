# 项目集操作栏间距 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 统一项目集树中项目集行与项目行操作按钮的左边界和间距规则。

**Architecture:** `ProgramsView.vue` 在项目集列表操作容器设定 `--workflow-action-gap: 6px`。`WorkflowActionButtons.vue` 的外层和主动作 flex 间距读取该变量并保留各自默认值，因而只影响项目集列表。

**Tech Stack:** Vue 3, scoped CSS, Node.js source-contract tests, Vite.

---

### Task 1: 锁定统一间距契约

**Files:**
- Create: `frontend/src/views/programActionSpacing.test.mjs`
- Modify: `frontend/src/views/ProgramsView.vue:58-84`
- Modify: `frontend/src/components/WorkflowActionButtons.vue:493-507`

**Step 1:** 写入失败测试，断言项目集列表操作容器声明 `--workflow-action-gap: 6px`，并断言共享组件的两个 flex 容器均使用该变量。

**Step 2:** 运行 `node src/views/programActionSpacing.test.mjs`，确认在现有源码上失败。

**Step 3:** 在项目集列表容器设置变量，将共享组件的两层 gap 改为 `var(--workflow-action-gap, <default>)`。

**Step 4:** 重跑该用例，确认通过。

### Task 2: 回归验证

**Files:**
- Verify: `frontend/src/views/ProgramsView.vue`
- Verify: `frontend/src/components/WorkflowActionButtons.vue`

**Step 1:** 运行 `npm test`，记录任何既有无关失败。

**Step 2:** 运行 `npm run build`。

**Step 3:** 运行 `git diff --check`，待主上确认交付方式后执行 Git 操作。
