# 工作流方案详情操作栏分组 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将工作流方案详情页的导航操作和保存操作分为左右两个紧凑分组。

**Architecture:** 只在 `WorkflowView.vue` 的详情页操作栏中增加语义分组容器，并用该视图的 scoped CSS 覆盖全局操作栏的均分布局。现有事件处理、权限和按钮条件不变。

**Tech Stack:** Vue 3、Element Plus、Vite、Node.js 测试脚本。

---

### Task 1: 覆盖详情页操作栏结构

**Files:**
- Modify: `frontend/src/views/WorkflowView.vue:76-100`
- Test: `frontend/src/views/workflowViewDetailActionBar.test.mjs`

**Step 1: Write the failing test**

新增源码结构测试，断言详情页操作栏存在 `workflow-detail-actions__navigation` 和 `workflow-detail-actions__editing` 两个容器，并分别包含返回操作与生命周期/保存操作。

**Step 2: Run test to verify it fails**

Run: `node --test frontend/src/views/workflowViewDetailActionBar.test.mjs`

Expected: FAIL，因为分组容器尚不存在。

**Step 3: Write minimal implementation**

在详情页的 `page-actions` 内包裹两组按钮。保留按钮的条件渲染、类型、loading 状态和 click handler。

**Step 4: Run test to verify it passes**

Run: `node --test frontend/src/views/workflowViewDetailActionBar.test.mjs`

Expected: PASS。

### Task 2: 固定桌面和窄屏布局

**Files:**
- Modify: `frontend/src/views/WorkflowView.vue:style scoped`
- Test: `frontend/src/views/workflowViewDetailActionBar.test.mjs`

**Step 1: Write the failing test**

添加断言：局部样式使用两端对齐的 `justify-content: space-between`，两个分组使用紧凑 `gap`，并在小屏断点允许换行且不沿用全局纵向单列规则。

**Step 2: Run test to verify it fails**

Run: `node --test frontend/src/views/workflowViewDetailActionBar.test.mjs`

Expected: FAIL，因为局部响应式样式不存在。

**Step 3: Write minimal implementation**

增加局部 CSS：桌面端两个分组分别靠两侧，组内按钮紧凑排列；中小屏允许组间换行，最小屏幕组内按钮纵向排列。

**Step 4: Run test to verify it passes**

Run: `node --test frontend/src/views/workflowViewDetailActionBar.test.mjs`

Expected: PASS。

### Task 3: 全量验证

**Files:**
- Verify: `frontend/src/views/WorkflowView.vue`

**Step 1: Run the frontend test suite**

Run: `npm test`

Expected: PASS，且新增结构测试被执行。

**Step 2: Build production assets**

Run: `npm run build`

Expected: exit code 0。

**Step 3: Inspect the resulting diff**

Run: `git diff --check && git status --short`

Expected: 无空白错误，且只包含本任务的视图、测试和计划文件改动。
