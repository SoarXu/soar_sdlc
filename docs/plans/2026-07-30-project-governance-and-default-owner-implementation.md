# 项目治理权限与默认负责人 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 允许任意登录用户创建项目并默认成为负责人，统一项目及项目集负责人对下属项目的治理权限。

**Architecture:** 后端集中计算项目治理者，组合当前或上级项目负责人、项目集负责人和系统管理员。创建控制器默认负责人为当前用户；两个前端创建页面预填当前用户，并据统一规则显示项目治理操作。非管理员治理者只能删除空叶子项目，系统管理员保留级联删除能力。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest、Vue 3、Node.js `assert`。

### Task 1: 锁定服务端授权契约

**Files:**
- Create: `backend/tests/test_project_governance_permissions.py`
- Modify: `backend/app/services/project_permission_service.py`
- Modify: `backend/app/controllers/project_controller.py`

**Step 1:** 写入普通用户创建、服务端默认负责人、项目负责人祖先、项目集负责人和项目配置/删除授权的失败测试；验证非管理员不能删除含子项目或工作项的项目。

**Step 2:** 运行 `pytest tests/test_project_governance_permissions.py -q`，确认旧规则失败。

**Step 3:** 实现统一项目治理计算、默认负责人和项目 ID 级删除校验。

**Step 4:** 重跑测试确认通过。

### Task 2: 锁定前端默认负责人和治理入口

**Files:**
- Create: `frontend/src/views/projectDefaultOwner.test.mjs`
- Modify: `frontend/src/views/ProgramsView.vue`
- Modify: `frontend/src/views/ProjectsView.vue`

**Step 1:** 写入两个创建表单预填当前用户、任意登录用户可创建顶级项目、项目负责人及项目集负责人可见治理操作的失败测试。

**Step 2:** 运行 `node src/views/projectDefaultOwner.test.mjs`，确认旧实现失败。

**Step 3:** 预填负责人、开放创建入口，并按项目与项目集祖先链计算项目列表的治理操作可见性。

**Step 4:** 重跑测试确认通过。

### Task 3: 回归验证

**Step 1:** 运行新增后端权限测试、项目权限 API 回归测试与前端默认负责人测试。

**Step 2:** 运行 `npm run build` 与 `git diff --check`。

**Step 3:** 得到主上确认后再提交、推送或合并。
