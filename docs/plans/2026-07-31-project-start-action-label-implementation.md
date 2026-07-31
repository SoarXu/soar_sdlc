# Project Start Action Label Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将项目工作流的 `start` 动作显示名统一为“启动”。

**Architecture:** 通过 Alembic 数据迁移更新已有项目工作流流转的 `action_name` 与表单文案。前端继续使用后端返回的动作名称，避免维护项目专用映射。

**Tech Stack:** Python、SQLAlchemy、Alembic、pytest、Vue 3。

### Task 1: 固化项目启动动作的迁移行为

**Files:**
- Create: `backend/alembic/versions/20260731_001_rename_project_start_action.py`
- Modify: `backend/tests/test_project_iteration_state_migration.py`

**Step 1: Write the failing test**

在现有迁移测试中创建项目和迭代的 `start` 流转，并分别设为“开始”。断言运行迁移后项目流转及 `form_config.title`、`submit_text` 为“启动”，迭代仍为“开始”。

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_project_iteration_state_migration.py -q`
Expected: FAIL，因为迁移尚不存在。

**Step 3: Write minimal implementation**

新增迁移，仅筛选 `workflow_definitions.object_type = 'project'` 与 `workflow_transitions.action_key = 'start'`，更新动作名称及 JSON 表单文案。

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_project_iteration_state_migration.py -q`
Expected: PASS。

### Task 2: 验证默认模板与运行时接口

**Files:**
- Test: `backend/tests/test_default_workflow_templates_api.py`
- Test: `backend/tests/test_program_project_api.py`

**Step 1: Add assertions**

断言项目的 `start` 流转名称为“启动”，而非项目对象不受影响。

**Step 2: Run focused backend tests**

Run: `pytest backend/tests/test_default_workflow_templates_api.py backend/tests/test_program_project_api.py -q`
Expected: PASS。

### Task 3: Complete verification

**Files:**
- Verify: changed migration and tests

**Step 1: Run backend regression tests**

Run: `pytest backend/tests/test_project_iteration_state_migration.py backend/tests/test_default_workflow_templates_api.py backend/tests/test_program_project_api.py -q`
Expected: PASS。

**Step 2: Run frontend regression tests**

Run: `npm test` from `frontend`
Expected: PASS。

**Step 3: Validate change scope**

Run: `git diff --check`
Expected: no output.
