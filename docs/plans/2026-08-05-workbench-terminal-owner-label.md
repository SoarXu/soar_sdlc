# 工作台终态处理人标签 Implementation Plan

**Goal:** 在工作台终态列表中显示“最后处理人”，准确表达保留的 `owner_id` 语义。

**Architecture:** 在 `DashboardView.vue` 中由当前列表页签计算处理人列名，模板绑定该
计算值；不修改后端工作台响应或数据模型。

---

### Task 1: 增加失败的前端契约测试

**Files:**
- Modify: `frontend/src/utils/workbenchViewModel.test.mjs`
- Modify: `frontend/src/views/DashboardView.vue`

1. 读取 `DashboardView.vue`，断言存在基于 `activeListSection.key` 的处理人列名计算，
并在 `completed`、`terminated` 返回“最后处理人”。
2. 运行 `node src/utils/workbenchViewModel.test.mjs`，确认测试因实现缺失失败。
3. 新增最小计算属性并将列的 `label` 绑定至该属性。
4. 重运行该测试，确认通过。

### Task 2: 回归验证

**Files:**
- Verify: `frontend/src/views/DashboardView.vue`

1. 运行 `npm test`。
2. 运行 `npm run build`。
3. 运行 `git diff --check`。
