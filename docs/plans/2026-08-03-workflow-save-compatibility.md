# 工作流保存兼容性修复 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让项目和 Bug 工作流可保存，同时保持工作流配置的字段校验边界。

**Architecture:** 前端序列化层删除不属于可编辑配置的迁移标记；后端校验层接受默认 Bug 模板实际使用的 `allow_unassigned`。两层均通过现有工作流保存测试覆盖。

**Tech Stack:** Vue 3、Node source-contract tests、FastAPI、Pytest。

### Task 1: Drop the project migration marker from saved UI configuration

**Files:**
- Modify: `frontend/src/utils/workflowTransitionConfig.js`
- Test: `frontend/src/utils/workflowTransitionConfig.test.mjs`

**Step 1: Write a failing serializer test**

Create a transition with `ui_config.migration_origin`, serialize it, and assert the result omits `migration_origin` while preserving `button_type` and normalized `list_display`.

**Step 2: Verify the failure**

Run: `node src/utils/workflowTransitionConfig.test.mjs`

Expected: FAIL because `migration_origin` is still present.

**Step 3: Implement the minimal serializer change**

Extend the existing UI configuration cleanup loop in `serializeWorkflowTransition` to delete `migration_origin`.

**Step 4: Verify the test passes**

Run: `node src/utils/workflowTransitionConfig.test.mjs`

Expected: PASS.

### Task 2: Accept the Bug template's unassigned-handler form option

**Files:**
- Modify: `backend/app/services/workflow_definition_service.py`
- Test: `backend/tests/test_workflow_definition_api.py`

**Step 1: Write a failing API test**

Save a Bug workflow transition containing `form_config: {"allow_unassigned": true, "fields": [...]}` and assert HTTP 200. Retain the existing test that rejects unrelated form configuration keys.

**Step 2: Verify the failure**

Run: `pytest tests/test_workflow_definition_api.py -k allow_unassigned -v`

Expected: FAIL with `Unsupported form configuration`.

**Step 3: Implement the minimal validation change**

Add `allow_unassigned` to `FORM_CONFIG_KEYS`; do not alter validation for any other key.

**Step 4: Verify the test passes**

Run: `pytest tests/test_workflow_definition_api.py -k allow_unassigned -v`

Expected: PASS.

### Task 3: Verify end-to-end save compatibility

**Files:**
- Verify only.

**Step 1: Run focused frontend and backend tests**

Run: `node src/utils/workflowTransitionConfig.test.mjs`

Run: `pytest tests/test_workflow_definition_api.py -v`

**Step 2: Call the live API with frontend-serialized project and Bug graphs**

Use the current graph payloads for the default scheme and verify both `PUT /workflow-definitions/{id}/graph` responses are HTTP 200.

**Step 3: Check whitespace**

Run: `git diff --check`

Expected: no output and exit code 0.
