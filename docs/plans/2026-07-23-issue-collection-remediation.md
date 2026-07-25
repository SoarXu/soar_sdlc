# 问题收集集中处理实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 完成 `issue.md` 中的界面一致性、项目生命周期、工作台覆盖范围和工作流方案完整性修复。

**Architecture:** 将项目生命周期与工作项代处理在工作流运行时明确分支；将列表动作展示规则集中到现有工作流动作辅助函数；扩展工作台服务的数据装配；在工作流方案服务和迁移中修复、阻止重复定义。

**Tech Stack:** Vue 3、Element Plus、FastAPI、SQLAlchemy、pytest、Node.js 测试运行器。

---

### Task 1: 修复项目生命周期的代处理原因

**Files:**
- Modify: `backend/app/services/workflow_runtime_service.py`
- Test: `backend/tests/test_workflow_runtime_api.py`

**Step 1: 编写失败测试**

验证项目负责人、项目集继承负责人和系统管理员执行项目 `start`、`suspend`、`close` 时不需要 `delegate_reason`；需求、任务和 Bug 的管理员代处理仍返回 `Delegate reason is required`。

**Step 2: 验证红灯**

Run: `pytest backend/tests/test_workflow_runtime_api.py -k delegate -v`

**Step 3: 最小实现**

仅当 `object_type` 为 `project` 时将代处理判断固定为 `False`；保留工作项原有 `_is_delegated` 行为。

**Step 4: 验证绿灯并提交**

Run: `pytest backend/tests/test_workflow_runtime_api.py -k delegate -v`

### Task 2: 统一项目列表和项目集列表的生命周期操作列

**Files:**
- Modify: `frontend/src/utils/workflowRuntimeActions.js`
- Modify: `frontend/src/components/WorkflowActionButtons.vue`
- Modify: `frontend/src/views/ProjectsView.vue`
- Modify: `frontend/src/views/ProgramsView.vue`
- Modify: `frontend/src/styles.css`
- Test: `frontend/src/components/workflowActionButtonsBehavior.test.mjs`
- Test: `frontend/src/views/programActionOrder.test.mjs`

**Step 1: 编写失败测试**

断言项目对象在列表中将 `start`、`suspend`、`close` 归为直接动作；断言两个列表的操作列保留一致的按钮类与删除按钮尺寸。

**Step 2: 验证红灯**

Run: `npm test -- workflowActionButtonsBehavior programActionOrder`

**Step 3: 最小实现**

为项目动作定义直接展示优先级，调整两个列表的操作列宽度和统一的按钮样式；不改变需求、任务、Bug 的动作分组。

**Step 4: 验证绿灯并提交**

Run: `npm test -- workflowActionButtonsBehavior programActionOrder`

### Task 3: 明确分派规则方案术语

**Files:**
- Modify: `frontend/src/views/ProjectsView.vue`
- Test: `frontend/src/views/projectCreationPermission.test.mjs`

**Step 1: 编写失败测试**

断言项目列表将列名显示为“分派规则方案”，且空 `assignee_rule_config_id` 显示“默认系统工作流”。

**Step 2: 验证红灯、实现、验证绿灯并提交**

Run: `npm test -- projectCreationPermission`

### Task 4: 在工作台纳入任务和 Bug

**Files:**
- Modify: `backend/app/services/dashboard_service.py`
- Modify: `frontend/src/utils/workbenchViewModel.js`
- Test: `backend/tests/test_dashboard_workbench_api.py`
- Test: `frontend/src/utils/workbenchViewModel.test.mjs`

**Step 1: 编写失败测试**

覆盖任务和 Bug 的待处理、我发起、项目范围过滤，以及工作台前端对象类型标签、跳转和工作流动作。

**Step 2: 验证红灯**

Run: `pytest backend/tests/test_dashboard_workbench_api.py -v`

Run: `npm test -- workbenchViewModel`

**Step 3: 最小实现**

在后端各工作台分区加载任务和 Bug，在前端视图模型中为两种对象复用现有标题、状态、动作和跳转映射。

**Step 4: 验证绿灯并提交**

Run: `pytest backend/tests/test_dashboard_workbench_api.py -v`

Run: `npm test -- workbenchViewModel`

### Task 5: 修复并防止工作流方案重复 Bug 定义

**Files:**
- Create: `backend/alembic/versions/20260723_001_disable_duplicate_bug_definition.py`
- Modify: `backend/app/services/assignee_rule_config_service.py`
- Modify: `backend/app/services/workflow_state_service.py`
- Test: `backend/tests/test_assignee_rule_config_api.py`
- Test: `backend/tests/test_test_case_execution_api.py`

**Step 1: 编写失败测试**

覆盖方案 `1` 的重复 Bug 定义修复后提 Bug 成功；新建或启用重复定义被拒绝；冲突错误包含中文对象类型和定义标识。

**Step 2: 验证红灯**

Run: `pytest backend/tests/test_assignee_rule_config_api.py backend/tests/test_test_case_execution_api.py -v`

**Step 3: 最小实现**

迁移停用 `debug-def`（ID `466`），服务端在保存、启用方案时阻止同方案同对象类型的多条启用定义；运行时错误携带冲突定义信息并使用中文提示。

**Step 4: 验证绿灯并提交**

Run: `pytest backend/tests/test_assignee_rule_config_api.py backend/tests/test_test_case_execution_api.py -v`

### Task 6: 完整回归

**Files:**
- Test: `backend/tests/test_workflow_runtime_api.py`
- Test: `backend/tests/test_dashboard_workbench_api.py`
- Test: `frontend`

**Step 1: 执行后端相关回归**

Run: `pytest backend/tests/test_workflow_runtime_api.py backend/tests/test_dashboard_workbench_api.py backend/tests/test_assignee_rule_config_api.py backend/tests/test_test_case_execution_api.py -v`

**Step 2: 执行前端测试和构建**

Run: `npm test`

Run: `npm run build`

**Step 3: 提交最终修复**

按变更组分别提交；不纳入当前工作区已有的无关改动。
