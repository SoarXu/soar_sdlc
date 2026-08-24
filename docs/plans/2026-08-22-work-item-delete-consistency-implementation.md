# 工作项删除一致性 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 允许已完成任务按既有权限删除，并阻断删除存在未删除关联任务的需求。

**Architecture:** 将需求任务关联检查放入 `delete_requirement()` 的首个写入前步骤，以稳定 `409` 契约返回冲突；各任务页面复用现有删除权限工具，不按终态分叉。

**Tech Stack:** FastAPI、SQLAlchemy、pytest、Vue 3、Node.js 契约测试、Vite。

---

### Task 1: 需求删除阻断 API

**Files:**
- Modify: `backend/app/services/requirement_service.py`
- Create: `backend/tests/test_requirement_delete_linked_tasks_api.py`

1. 写入失败测试：创建带根、子任务的需求并删除，断言 `409 REQUIREMENT_HAS_LINKED_TASKS`、数量正确、需求/任务关联/审计均未变化；已删除任务不阻断。
2. 运行 `cd backend && pytest tests/test_requirement_delete_linked_tasks_api.py -v`，确认当前实现错误地返回 `204`。
3. 在任何写入前统计未删除关联任务，抛出稳定结构化 `409`；保留无任务需求原有删除路径。
4. 重跑聚焦测试确认通过。

### Task 2: 已完成任务删除入口

**Files:**
- Modify: `frontend/src/views/TasksView.vue`
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/views/TaskDetailView.vue`
- Create: `frontend/src/views/workItemDeleteConsistency.test.mjs`

1. 写入失败源契约，要求三个任务入口不以终态隐藏删除，并要求需求删除调用统一错误反馈。
2. 运行 `cd frontend && node src/views/workItemDeleteConsistency.test.mjs`，确认因缺少统一入口而失败。
3. 以现有 `canDeleteWorkItem`、项目关闭和迭代可变性判断统一入口；详情页补齐删除确认及刷新/跳转。
4. 重跑聚焦前端测试确认通过。

### Task 3: 回归与问题清单

**Files:**
- Modify after evidence: `docs/issues/2026-08-22-后续问题清单.md`

1. 运行后端聚焦与关联回归、前端聚焦测试、`npm test`、`npm run build`、`git diff --check`。
2. 记录精确命令、通过数量和仍需页面验收的范围，将 N-006 更新为待验证或已解决（仅在全部验收完成后）。
3. 不在用户选择交付方式前提交、合并、推送或重启服务。
