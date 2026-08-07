# 项目成员可见范围 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 非项目成员不能通过列表、搜索或直达链接查看项目及其关联资源，组件成员不会隐式获得项目成员资格。

**Architecture:** 在项目权限服务集中计算用户可见项目并校验单个项目访问；各资源服务按可见项目集合过滤列表，控制器在详情及项目子资源端点校验访问。维护组件创建仅创建组件配置，不复制来源成员。

**Tech Stack:** FastAPI, SQLAlchemy, pytest, Vue 3.

---

### Task 1: 定义失败回归

**Files:**
- Modify: `backend/tests/test_project_permission_boundary_api.py`
- Modify: `backend/tests/test_business_components_api.py`

**Step 1:** 写入非成员无法列出或直达项目、需求、任务、Bug、测试、迭代和组件的测试；写入创建组件不复制来源成员的测试。

**Step 2:** 运行相关 pytest，确认因当前未过滤查询和自动复制成员而失败。

### Task 2: 集中项目查看权限

**Files:**
- Modify: `backend/app/services/project_permission_service.py`
- Modify: `backend/app/services/project_service.py`
- Modify: `backend/app/services/requirement_service.py`
- Modify: `backend/app/services/task_service.py`
- Modify: `backend/app/services/bug_service.py`

**Step 1:** 新增可见项目集合与单项目查看校验，复用现有系统管理员、项目成员和治理权限模型。

**Step 2:** 令项目和工作项列表按可见项目集合查询；详情在返回实体前进行校验。

**Step 3:** 运行任务 1 测试，确认通过。

### Task 3: 保护关联资源和组件创建

**Files:**
- Modify: `backend/app/controllers/project_controller.py`
- Modify: `backend/app/controllers/requirement_controller.py`
- Modify: `backend/app/controllers/task_controller.py`
- Modify: `backend/app/controllers/bug_controller.py`
- Modify: `backend/app/controllers/business_component_controller.py`
- Modify: `backend/app/services/business_component_service.py`

**Step 1:** 向读取端点注入当前用户，保护项目子资源、工作项辅助资源和组件读取。

**Step 2:** 移除维护组件创建时来源成员向目标项目和组件的自动复制。

**Step 3:** 运行任务 1 测试与现有业务组件测试，确认通过。

### Task 4: 全量验证与问题归档

**Files:**
- Modify: `docs/issues/2026-08-07-后续问题清单.md`

**Step 1:** 运行权限、组件、关联工作项及前端构建回归。

**Step 2:** 更新 N-001 状态、执行计划和验证结果。

**Step 3:** 执行 `git diff --check`，检查差异和工作区范围。
