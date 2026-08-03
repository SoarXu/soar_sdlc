# 默认工作流方案空白流程回填 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 自动恢复系统默认工作流方案中缺失或完全空白的需求、任务和 Bug 工作流，同时保护任何已有自定义流程。

**Architecture:** 在 `ensure_default_assignee_rule_config` 完成旧默认方案识别后，调用一个幂等的回填辅助函数。该函数读取系统标准模板，只为缺失或状态与流转均为空的定义创建并复制流程图；非空定义原样保留。

**Tech Stack:** FastAPI、SQLAlchemy、Pytest、MySQL。

### Task 1: Add regression coverage for blank default-scheme workflows

**Files:**
- Modify: `backend/tests/test_assignee_rule_config_api.py`
- Modify: `backend/app/services/assignee_rule_config_service.py`

**Step 1: Write the failing test**

Add a test that creates an otherwise blank temporary workflow scheme, invokes the new backfill helper, and asserts that its `requirement`、`task` and `bug` graphs have an initial state, states and transitions. Add a second assertion that a graph already copied from the system template retains its state and transition IDs after backfill.

**Step 2: Run the targeted test to verify it fails**

Run: `pytest tests/test_assignee_rule_config_api.py -k default_workflow_backfill -v`

Expected: FAIL because the backfill helper does not exist.

**Step 3: Implement the minimal backfill helper**

In `assignee_rule_config_service.py`, add a private helper that:

```python
def _backfill_empty_workflows(db: Session, config: AssigneeRuleConfig) -> None:
    ensure_default_workflow_templates(db)
    sources = _source_definitions(db, SimpleNamespace(
        source_type="system", source_id="system-standard"
    ))
    # Create a definition when missing; clone only when both states and transitions are empty.
```

Use `SCHEME_WORKFLOW_OBJECT_TYPES` filtered to `requirement`、`task`、`bug`; create missing definitions with the same fields as `create_config`; reuse `_clone_graph` so initial-state references and transition state references are copied correctly.

**Step 4: Verify the test passes**

Run: `pytest tests/test_assignee_rule_config_api.py -k default_workflow_backfill -v`

Expected: PASS.

### Task 2: Invoke recovery only for the system default scheme

**Files:**
- Modify: `backend/app/services/assignee_rule_config_service.py`
- Test: `backend/tests/test_assignee_rule_config_api.py`

**Step 1: Write the failing API-level test**

Add coverage proving that listing workflow schemes recovers the default scheme's empty work-item definitions, while a separately-created blank scheme remains empty.

**Step 2: Run the targeted test to verify it fails**

Run: `pytest tests/test_assignee_rule_config_api.py -k default_scheme_recovery -v`

Expected: FAIL because listing schemes does not yet invoke recovery.

**Step 3: Wire the helper into default-scheme initialization**

Call `_backfill_empty_workflows` only after `ensure_default_assignee_rule_config` resolves or creates the default configuration. Commit only when the helper added or restored graph data; preserve the existing behavior for every non-default scheme.

**Step 4: Verify the test passes**

Run: `pytest tests/test_assignee_rule_config_api.py -k "default_workflow_backfill or default_scheme_recovery" -v`

Expected: PASS.

### Task 3: Run regression verification

**Files:**
- Verify only.

**Step 1: Run the affected backend test module**

Run: `pytest tests/test_assignee_rule_config_api.py -v`

Expected: PASS.

**Step 2: Run workflow-definition regression tests**

Run: `pytest tests/test_workflow_definition_api.py tests/test_default_workflow_templates_api.py -v`

Expected: PASS.

**Step 3: Check the staged diff**

Run: `git diff --check`

Expected: no output and exit code 0.
