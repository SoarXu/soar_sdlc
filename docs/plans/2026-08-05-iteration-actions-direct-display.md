# 迭代动作直显 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在迭代详情页、迭代列表和项目详情页将当前可执行的迭代生命周期动作直接显示，取消“更多”菜单。

**Architecture:** 三个目标入口均复用 `WorkflowActionButtons` 并传入 `object-type="iteration"`。在 `splitListActions()` 增加迭代对象的直显规则，使其所有已排序的可见动作进入 `primaryActions`、不产生 `moreActions`；不触及后端、工作流配置或页面模板。

**Tech Stack:** Vue 3、Element Plus、Node.js `assert`、Vite。

---

### Task 1: 为迭代动作分组建立回归测试

**Files:**
- Modify: `frontend/src/utils/workflowRuntimeActions.test.mjs`
- Verify: `frontend/src/utils/workflowRuntimeActions.js`

**Step 1: Write the failing test**

在现有 `splitListActions` 用例之后添加迭代用例：输入 `start`、`complete`、`cancel` 三个 `list_display: 'more'` 的动作，按 `sort_order` 断言三者全部位于 `primaryActions`，且 `moreActions` 为空。

**Step 2: Run test to verify it fails**

Run: `node src/utils/workflowRuntimeActions.test.mjs`（工作目录：`frontend`）

Expected: FAIL，当前实现会将三个迭代动作置于 `moreActions`。

**Step 3: Write minimal implementation**

在 `frontend/src/utils/workflowRuntimeActions.js` 的 `splitListActions()` 中，将迭代对象的可见动作集合视为直接动作；继续保留项目 `start`、`suspend`、`close` 的既有直显规则和其他对象的配置分组逻辑。

**Step 4: Run test to verify it passes**

Run: `node src/utils/workflowRuntimeActions.test.mjs`（工作目录：`frontend`）

Expected: PASS，迭代动作直显断言及既有项目、需求分组断言全部通过。

### Task 2: 执行前端回归验证

**Files:**
- Verify: `frontend/src/components/WorkflowActionButtons.vue`
- Verify: `frontend/src/views/IterationDetailView.vue`
- Verify: `frontend/src/views/IterationsView.vue`
- Verify: `frontend/src/views/ProjectDetailView.vue`

**Step 1: Run the frontend test suite**

Run: `npm test`（工作目录：`frontend`）

Expected: PASS，现有组件、工作流与视图源契约测试无回归。

**Step 2: Run the production build**

Run: `npm run build`（工作目录：`frontend`）

Expected: PASS，Vite 构建完成且没有编译错误。

**Step 3: Check the final diff**

Run: `git diff --check`

Expected: PASS，无空白错误。

**Step 4: Defer Git delivery**

不执行暂存、提交、推送、创建 PR 或合并；实现完成后由主上选择交付方式。
