# Bug 列表操作列宽度 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 使全局 Bug 列表的操作列完整显示所有当前可见操作。

**Architecture:** 保持共享 `workflowActionColumnWidth()` 的动态工作流动作计算。仅在 Bug 列表补足关注、删除和外层间距所需的静态空间，使固定列宽度随当前工作流动作继续增长。

**Tech Stack:** Vue 3、Node.js `assert`、Vite。

---

### Task 1: 建立 Bug 操作列宽度回归契约

**Files:**
- Create: `frontend/src/views/bugListActionColumnWidth.test.mjs`
- Modify: `frontend/src/views/BugsView.vue`

**Step 1: Write the failing test**

创建源契约测试，读取 `BugsView.vue` 并断言其列宽计算包含：

```javascript
{ minWidth: 240, extraWidth: 160 }
```

**Step 2: Run test to verify it fails**

Run: `node src/views/bugListActionColumnWidth.test.mjs`（工作目录：`frontend`）

Expected: FAIL，当前页面使用 `{ minWidth: 180, extraWidth: 90 }`。

**Step 3: Write minimal implementation**

将 `BugsView.vue` 中的列宽选项改为：

```javascript
{ minWidth: 240, extraWidth: 160 }
```

**Step 4: Run test to verify it passes**

Run: `node src/views/bugListActionColumnWidth.test.mjs`（工作目录：`frontend`）

Expected: PASS，Bug 页面已为关注、删除和间距预留足够宽度，工作流动作仍由共享函数动态计算。

### Task 2: 执行前端回归验证

**Files:**
- Verify: `frontend/src/utils/workflowActionColumn.js`
- Verify: `frontend/src/components/WatchToggleButton.vue`
- Verify: `frontend/src/views/BugsView.vue`

**Step 1: Run the frontend test suite**

Run: `npm test`（工作目录：`frontend`）

Expected: PASS，工作流列宽、关注按钮和 Bug 视图测试无回归。

**Step 2: Run the production build**

Run: `npm run build`（工作目录：`frontend`）

Expected: PASS，Vite 构建完成且没有编译错误。

**Step 3: Check the final diff**

Run: `git diff --check`

Expected: PASS，无空白错误。

**Step 4: Defer Git delivery**

不执行暂存、提交、推送、创建 PR 或合并；实现完成后由主上选择交付方式。
