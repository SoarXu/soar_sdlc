# 同级项目名称唯一性 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 拒绝同一项目集、同一父项目下规范化名称相同的活动项目。

**Architecture:** 项目服务在创建和更新持久化前计算目标 `program_id + parent_id + normalized_name`，查询同级活动项目并在冲突时返回 HTTP 422。更新时排除当前项目；不同项目集、不同父项目和未绑定项目集不进入该校验。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest。

### Task 1: 锁定接口唯一性契约

**Files:**
- Create: `backend/tests/test_project_name_uniqueness.py`
- Modify: `backend/app/services/project_service.py:237-285`

**Step 1: 写入失败的 API 测试**

覆盖以下场景：

```python
assert duplicate.status_code == 422
assert duplicate.json()["detail"] == "项目名称已存在"
```

- 同项目集、同父项目下创建重复名称。
- 大小写或首尾空白变体。
- 重命名为同级名称。
- 移动至具有同名项目的目标父项目或项目集。
- 不同项目集、不同父项目和未绑定项目集同名可创建。

**Step 2: 运行测试并确认失败**

Run: `pytest tests/test_project_name_uniqueness.py -q`

Expected: FAIL，现有服务允许重复名称。

### Task 2: 实现服务层同级校验

**Files:**
- Modify: `backend/app/services/project_service.py:237-285`

**Step 1: 规范化待校验名称**

```python
normalized_name = name.strip().lower()
```

**Step 2: 实现目标作用域冲突检查**

仅当 `program_id` 非空时，查询 `deleted == 0`、同 `program_id`、同 `parent_id` 且规范化名称相同的项目；更新时排除当前项目。

**Step 3: 在创建与更新前调用校验**

创建使用已解析的项目集和父项目；更新以名称、父项目和项目集的最终值校验，覆盖重命名与移动。

**Step 4: 运行测试并确认通过**

Run: `pytest tests/test_project_name_uniqueness.py -q`

Expected: PASS。

### Task 3: 完整性检查与交付准备

**Files:**
- Verify: `backend/app/services/project_service.py`
- Verify: `backend/tests/test_project_name_uniqueness.py`

**Step 1:** 运行新增唯一性测试与项目权限回归测试。

**Step 2:** 搜索项目服务中重复名称错误详情，确认仅使用中文“项目名称已存在”。

**Step 3:** 运行 `git diff --check`。

**Step 4:** 得到主上确认后再提交、推送或合并。
