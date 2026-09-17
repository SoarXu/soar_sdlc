# 工作台导航状态保持 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让工作台筛选条件、当前页和每页条数在详情返回、浏览器导航、侧边栏重入和刷新时保持一致。

**Architecture:** 将工作台导航状态编码到路由查询参数。新增独立的解析/序列化工具，`DashboardView.vue` 在挂载时从路由恢复 refs，并在筛选和分页变化时用 `router.replace` 更新当前 URL；进入详情时携带工作台查询参数，详情页按 `from=dashboard` 返回同一组参数。

**Tech Stack:** Vue 3 Composition API、Vue Router 4、Node.js 内置 `node:test` 风格断言、Vite。

---

### Task 1: Add route-state utility tests

**Files:**
- Create: `frontend/src/utils/workbenchRouteState.test.mjs`
- Create: `frontend/src/utils/workbenchRouteState.js`

**Step 1: Write the failing test**

覆盖默认状态、字符串与多选参数往返、非法页码/页大小回退，以及空数组不生成参数。

**Step 2: Run test to verify it fails**

Run: `npm test workbenchRouteState.test.mjs` from `frontend`

Expected: FAIL because the utility module does not exist.

**Step 3: Write minimal implementation**

实现 `parseWorkbenchRouteState(query)`、`serializeWorkbenchRouteState(state)` 和 `workbenchRouteQuery(state)`，统一处理关键词、六类多选筛选、`page`、`page_size`。

**Step 4: Run test to verify it passes**

Run: `npm test workbenchRouteState.test.mjs`

Expected: PASS。

### Task 2: Restore and synchronize DashboardView route state

**Files:**
- Modify: `frontend/src/views/DashboardView.vue`
- Create: `frontend/src/views/workbenchRouteState.test.mjs`

**Step 1: Write the failing test**

增加源码契约测试，确认视图使用 `useRoute`、初始化解析工具、筛选/分页通过 `router.replace` 同步，并将查询参数传入详情链接。

**Step 2: Run test to verify it fails**

Run: `npm test workbenchRouteState.test.mjs`

Expected: FAIL because DashboardView currently only uses local refs and detail links只有 `from=dashboard`。

**Step 3: Write minimal implementation**

在工作台引入 `useRoute` 和状态工具；挂载时先按查询参数初始化 refs，再加载数据；筛选/分页变更时更新当前工作台 URL。将当前查询参数合并到需求、任务和 Bug 详情链接中，避免进入详情时丢失上下文。

**Step 4: Run test to verify it passes**

Run: `npm test workbenchRouteState.test.mjs`

Expected: PASS。

### Task 3: Preserve route state in detail-page return actions

**Files:**
- Modify: `frontend/src/views/RequirementDetailView.vue`
- Modify: `frontend/src/views/TaskDetailView.vue`
- Modify: `frontend/src/views/BugDetailView.vue`
- Create: `frontend/src/views/workbenchDetailBackNavigation.test.mjs`

**Step 1: Write the failing test**

确认三类详情页在 `from=dashboard` 分支返回 dashboard 时，会保留当前路由中除 `from` 外的工作台查询参数。

**Step 2: Run test to verify it fails**

Run: `npm test workbenchDetailBackNavigation.test.mjs`

Expected: FAIL because当前实现返回 dashboard 时没有携带查询参数。

**Step 3: Write minimal implementation**

抽取或复用查询参数构造逻辑，仅在 `from=dashboard` 返回分支传递工作台状态；其他来源（项目、迭代、全局列表）保持现有返回行为。

**Step 4: Run test to verify it passes**

Run: `npm test workbenchDetailBackNavigation.test.mjs`

Expected: PASS。

### Task 4: Run regression verification

**Files:**
- No production files expected.

**Step 1: Run focused tests**

Run: `npm test workbenchRouteState.test.mjs workbenchDetailBackNavigation.test.mjs dashboardWorkbenchTypeFilter.test.mjs`

Expected: PASS。

**Step 2: Run all frontend tests**

Run: `npm test`

Expected: PASS with no failures。

**Step 3: Build production bundle**

Run: `npm run build`

Expected: Vite build completes successfully。

**Step 4: Manually verify navigation**

在工作台设置筛选并切到非第一页，进入需求/任务/Bug详情后点击返回；再验证浏览器后退/前进和侧边栏离开重入，筛选、页码和每页条数均保持。
