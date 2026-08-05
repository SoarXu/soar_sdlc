# 迭代负责人权限边界 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 完成 N-003 至 N-006，并以 API、前端源契约和构建验证结果更新问题清单。

**Architecture:** 后端新增迭代负责人操作级授权并在迭代和工作流端点执行；前端通过同一职责边界控制入口。三个页面问题均以最小模板改动和源契约测试完成。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、Vue 3、Node.js assert、Vite。

---

### Task 1: 迭代负责人后端授权

**Files:**
- Modify: `backend/app/services/project_permission_service.py`
- Modify: `backend/app/controllers/iteration_controller.py`
- Modify: `backend/app/services/workflow_runtime_service.py`
- Test: `backend/tests/test_iteration_owner_permission_api.py`

1. 添加负责人、项目成员有效性、项目关闭和治理者覆盖的 API 失败用例。
2. 实现 `can_manage_iteration_as_owner`、查看和治理校验，以及覆盖原因校验。
3. 将详情、范围操作、编辑、删除和生命周期入口按操作级权限接入。
4. 运行 `pytest tests/test_iteration_owner_permission_api.py -q`。

### Task 2: 迭代负责人前端入口

**Files:**
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/views/IterationDetailView.vue`
- Test: `frontend/src/views/iterationOwnerPermission.test.mjs`

1. 编写负责人可见职责入口、普通成员不可见治理入口的源契约测试。
2. 仅显示负责人可执行的迭代编辑、范围和生命周期操作，保留治理者入口。
3. 运行 `node src/views/iterationOwnerPermission.test.mjs`。

### Task 3: N-004 阻断弹窗挂载

**Files:**
- Modify: `frontend/src/components/WorkflowActionButtons.vue`
- Modify: `frontend/src/components/workflowActionButtonsBehavior.test.mjs`

1. 断言阻断对话框使用 `append-to-body`。
2. 给 `blockerDialogVisible` 对话框补充该属性。
3. 运行 `node src/components/workflowActionButtonsBehavior.test.mjs`。

### Task 4: N-005 与 N-006 页面操作栏

**Files:**
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/views/projectDetailWorkflowIterationLayout.test.mjs`

1. 断言迭代操作使用 `.table-actions` 包装，需求操作不再固定渲染编辑按钮。
2. 以统一容器包装迭代动作，移除需求固定编辑入口。
3. 运行 `node src/views/projectDetailWorkflowIterationLayout.test.mjs`。

### Task 5: 回归与问题清单

**Files:**
- Modify: `docs/issues/2026-08-04-后续问题清单.md`

1. 运行新增定向测试、`npm test`、`npm run build` 和 `git diff --check`。
2. 记录命令和结果，将 N-003 至 N-006 状态更新为已解决。
3. 不提交、不推送、不创建 PR，等待主上选择交付方式。
