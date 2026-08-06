# List Filters Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为迭代、测试管理和 Bug 列表添加已确认的最小筛选集合。

**Architecture:** 各页面在本地数据与 `usePagination()` 之间增加过滤后的计算属性；页面状态仅保存在当前视图，改变条件时回到第 1 页。无接口或权限变更。

**Tech Stack:** Vue 3 Composition API、Element Plus、Node.js 源码契约测试。

---

### Task 1: 迭代筛选

**Files:**
- Modify: `frontend/src/views/IterationsView.vue`
- Create: `frontend/src/views/iterationListFilters.test.mjs`

1. 写入失败测试，断言迭代页仅提供项目和状态筛选，并将过滤数据传入分页。
2. 运行测试，确认失败。
3. 加入项目/状态筛选和重置按钮，筛选变化时重置迭代页码。
4. 运行测试，确认通过。

### Task 2: 测试管理筛选

**Files:**
- Modify: `frontend/src/views/TestsView.vue`
- Create: `frontend/src/views/testManagementFilters.test.mjs`

1. 写入失败测试，断言两个 Tab 各含关键词、项目筛选，并分别驱动用例库和测试单分页。
2. 运行测试，确认失败。
3. 为两个 Tab 添加独立筛选状态和清空动作；关键词仅匹配标题或名称。
4. 运行测试，确认通过。

### Task 3: Bug 列表筛选

**Files:**
- Modify: `frontend/src/views/BugsView.vue`
- Create: `frontend/src/views/bugListFilters.test.mjs`

1. 写入失败测试，断言 Bug 页仅提供项目、严重程度和状态筛选，并将过滤数据传入分页。
2. 运行测试，确认失败。
3. 加入筛选与重置动作，筛选变化时重置页码。
4. 运行测试，确认通过。

### Task 4: 完整验证

1. 运行三个新测试。
2. 运行 `npm test` 和 `npm run build`。
3. 运行 `git diff --check` 并更新相关问题记录（如有）。
