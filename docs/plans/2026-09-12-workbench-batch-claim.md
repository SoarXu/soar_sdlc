# 工作台批量认领 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在工作台增加按当前用户权限执行的批量认领能力。

**Architecture:** 后端为 `claim` 增加独立批量元数据与原子批处理接口；前端扩展工作项选择模型，并在现有批量操作栏中加入“认领”按钮。每条事项携带自己的工作流流转 ID，服务端统一事务执行。

**Tech Stack:** FastAPI、SQLAlchemy、Pydantic、Vue 3、Element Plus、Node test runner、pytest。

---

### Task 1: 后端批量认领契约与测试

**Files:**
- Modify: `backend/app/views/workflow_runtime_view.py`
- Modify: `backend/app/controllers/workflow_runtime_controller.py`
- Modify: `backend/app/services/workflow_runtime_service.py`
- Test: `backend/tests/test_workflow_runtime_api.py`

**Step 1: Write the failing tests**

覆盖 `claim` 元数据、成功批量认领、跨项目拒绝、非认领流转拒绝和整批回滚。

**Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_workflow_runtime_api.py -k "bulk_claim" -q`

Expected: FAIL because the response has no claim metadata and the endpoint is not implemented.

**Step 3: Implement the minimal backend**

新增 `WorkflowBulkClaimItem/Request/Read`，新增 `/workflow-runtime/claims/batch` 路由和 `execute_bulk_claim` 服务。认领元数据仅在动作 `claim`、项目有效且当前用户可执行时支持；服务端逐条调用现有 `_execute_transition(..., commit=False)`，全部成功后提交，否则回滚。

**Step 4: Run focused tests**

Run: `python -m pytest tests/test_workflow_runtime_api.py -k "bulk_claim" -q`

Expected: PASS。

### Task 2: 前端批量栏与选择逻辑

**Files:**
- Modify: `frontend/src/api/workflowRuntime.js`
- Modify: `frontend/src/utils/batchAssignmentSelection.js`
- Modify: `frontend/src/components/BatchAssignmentBar.vue`
- Modify: `frontend/src/views/DashboardView.vue`
- Test: `frontend/src/utils/batchAssignmentSelection.test.mjs`
- Test: `frontend/src/components/batchAssignmentBarBehavior.test.mjs`
- Test: `frontend/src/views/workItemBatchAssignment.test.mjs`

**Step 1: Write the failing tests**

覆盖认领流转识别、混合选择兼容、按钮文案、认领接口调用和完成事件。

**Step 2: Run tests to verify they fail**

Run: `npm test -- --runInBand` (from `frontend`)

Expected: FAIL because claim selection and button are absent。

**Step 3: Implement the minimal frontend**

扩展选择工具返回 `claim` 与 `assign` 能力；批量栏接收当前用户可用的认领行，显示“认领”按钮并调用新接口。工作台行选择允许具备任一批量能力的行，但仍限制同类型同项目。

**Step 4: Run focused tests**

Run: `node src/utils/batchAssignmentSelection.test.mjs`, `node src/components/batchAssignmentBarBehavior.test.mjs`, `node src/views/workItemBatchAssignment.test.mjs`

Expected: PASS。

### Task 3: 全量验证

**Files:**
- Test: `backend/tests/test_workflow_runtime_api.py`
- Test: frontend test suite

**Step 1: Run backend regression tests**

Run: `python -m pytest tests/test_workflow_runtime_api.py -q`

Expected: PASS。

**Step 2: Run frontend regression tests**

Run: `npm test` (from `frontend`)

Expected: PASS。

**Step 3: Inspect diff and Git state**

Run: `git diff --check; git status --short; git branch --show-current; git remote -v; git branch --list main master`

Expected: no whitespace errors; only scoped source/test/docs changes are attributed to this task, while pre-existing user changes remain untouched。
