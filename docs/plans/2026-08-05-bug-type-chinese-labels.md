# Bug 类型中文展示 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在项目详情、迭代详情的 Bug 列表和 Bug 详情中展示 Bug 类型的中文名称。

**Architecture:** 三个页面已通过 `useBugTypes()` 请求同一类型字典。仅解构其 `bugTypeLabel` 并替换展示位置，保持函数对未知类型的原值回退；不新增接口、静态映射或后端字段。

**Tech Stack:** Vue 3、Node.js `assert`、Vite。

---

### Task 1: 建立三处 Bug 类型展示的回归契约

**Files:**
- Create: `frontend/src/views/bugTypeDisplay.test.mjs`
- Verify: `frontend/src/views/ProjectDetailView.vue`
- Verify: `frontend/src/views/IterationDetailView.vue`
- Verify: `frontend/src/views/BugDetailView.vue`

**Step 1: Write the failing test**

创建源契约测试，读取三个 Vue 文件并断言：

```javascript
assert.match(projectDetail, /const \{ bugTypeOptions, bugTypeLabel \} = useBugTypes\(\)/)
assert.match(projectDetail, /bugTypeLabel\(row\.bug_type\)/)
assert.match(iterationDetail, /bugTypeLabel\(row\.bug_type\)/)
assert.match(bugDetail, /<el-descriptions-item label="Bug 类型">\{\{ bugTypeLabel\(bug\.bug_type\) \}\}<\/el-descriptions-item>/)
```

**Step 2: Run test to verify it fails**

Run: `node src/views/bugTypeDisplay.test.mjs`（工作目录：`frontend`）

Expected: FAIL，当前三个页面尚未在展示区调用 `bugTypeLabel`，Bug 详情缺少描述项。

**Step 3: Write minimal implementation**

在三个页面将 `const { bugTypeOptions } = useBugTypes()` 改为：

```javascript
const { bugTypeOptions, bugTypeLabel } = useBugTypes()
```

将两个列表的单元格改为：

```vue
{{ bugTypeLabel(row.bug_type) }}
```

在 `BugDetailView.vue` 的 `el-descriptions` 中新增：

```vue
<el-descriptions-item label="Bug 类型">{{ bugTypeLabel(bug.bug_type) }}</el-descriptions-item>
```

**Step 4: Run test to verify it passes**

Run: `node src/views/bugTypeDisplay.test.mjs`（工作目录：`frontend`）

Expected: PASS，三处中文标签展示契约全部满足。

### Task 2: 执行前端回归验证

**Files:**
- Verify: `frontend/src/utils/useBugTypes.js`
- Verify: `frontend/src/views/ProjectDetailView.vue`
- Verify: `frontend/src/views/IterationDetailView.vue`
- Verify: `frontend/src/views/BugDetailView.vue`

**Step 1: Run the frontend test suite**

Run: `npm test`（工作目录：`frontend`）

Expected: PASS，类型字典、详情与工作流相关测试无回归。

**Step 2: Run the production build**

Run: `npm run build`（工作目录：`frontend`）

Expected: PASS，Vite 构建完成且没有编译错误。

**Step 3: Check the final diff**

Run: `git diff --check`

Expected: PASS，无空白错误。

**Step 4: Defer Git delivery**

不执行暂存、提交、推送、创建 PR 或合并；实现完成后由主上选择交付方式。
