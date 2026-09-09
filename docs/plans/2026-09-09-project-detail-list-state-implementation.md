# 项目详情列表状态保持 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 保持项目详情页五类列表的独立筛选、分页和测试子标签状态。

**Architecture:** 新增项目列表路由状态解析/序列化工具，将五组状态编码到项目详情 URL。`ProjectDetailView.vue` 从 URL 恢复并用 `router.replace` 同步状态；详情链接和详情返回沿用完整项目查询参数。

**Tech Stack:** Vue 3、Vue Router 4、Node.js 测试脚本、Vite。

---

### Task 1: Add project list route-state utility

**Files:**
- Create: `frontend/src/utils/projectDetailRouteState.js`
- Create: `frontend/src/utils/projectDetailRouteState.test.mjs`

**Steps:**

1. 先写解析/序列化失败测试，运行 `npm test projectDetailRouteState.test.mjs` 确认模块缺失导致失败。
2. 实现需求、任务、测试用例、测试单、Bug 五组状态的独立解析/序列化，覆盖关键词、迭代筛选、页码、每页条数、`test_tab` 和非法值回退。
3. 运行同一命令确认测试通过。

### Task 2: Integrate ProjectDetailView state

**Files:**
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Create: `frontend/src/views/projectDetailRouteState.test.mjs`

**Steps:**

1. 先添加源码契约测试并运行确认当前视图缺少路由状态恢复、同步和详情查询传递。
2. 引入 `useRoute` 状态工具，挂载时恢复五组列表状态；筛选、分页和标签变化同步 URL，避免内部 `router.replace` 造成重复加载。
3. 需求、任务、测试用例和 Bug 详情链接带上完整项目查询参数；测试单入口保留 `test_tab`。
4. 运行项目详情聚焦测试。

### Task 3: Preserve state in detail back navigation

**Files:**
- Modify: `frontend/src/views/RequirementDetailView.vue`
- Modify: `frontend/src/views/TaskDetailView.vue`
- Modify: `frontend/src/views/TestCaseDetailView.vue`
- Modify: `frontend/src/views/BugDetailView.vue`
- Create: `frontend/src/views/projectDetailBackNavigation.test.mjs`

**Steps:**

1. 先写失败测试，确认四类详情的 `from=project` 返回未保留完整查询参数。
2. 在项目来源返回分支中保留 `route.query`，并继续使用原有 `tab` 行为。
3. 运行聚焦测试确认通过。

### Task 4: Regression verification

1. 运行 `npm test`，确认完整前端测试通过。
2. 运行 `npm run build`，确认生产构建成功。
3. 手动验证五类列表分别设置筛选和分页，切换标签、进入详情返回、浏览器前进/后退及离开项目重进均恢复。
