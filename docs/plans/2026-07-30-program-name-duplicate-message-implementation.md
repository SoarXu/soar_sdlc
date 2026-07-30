# 项目集重复名称提示中文化 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将项目集名称重复校验返回的提示统一改为“项目集名称已存在”。

**Architecture:** 后端服务层已将三条重复名称校验路径收敛到同一 HTTP 422 错误响应。仅替换响应的 `detail` 文案，并让现有接口测试与服务层异常测试断言该稳定的中文契约。

**Tech Stack:** Python、FastAPI、SQLAlchemy、pytest。

### Task 1: 锁定中文错误响应契约

**Files:**
- Modify: `backend/tests/test_program_name_uniqueness.py:35-38, 538, 578`

**Step 1: 更新重复名称接口断言为目标中文文案**

```python
assert response.json()["detail"] == "项目集名称已存在"
```

**Step 2: 更新数据库预校验和提交冲突异常断言**

```python
assert getattr(exc, "detail", None) == "项目集名称已存在"
assert raised.value.detail == "项目集名称已存在"
```

**Step 3: 运行测试，验证它在代码尚未更新前失败**

Run: `pytest tests/test_program_name_uniqueness.py -q`

Expected: FAIL，失败原因是服务仍返回英文错误文案。

### Task 2: 统一服务层的重复名称提示

**Files:**
- Modify: `backend/app/services/program_service.py:360, 376, 422`

**Step 1: 替换三条重复名称错误路径的 `detail`**

```python
detail="项目集名称已存在",
```

**Step 2: 运行测试，验证其通过**

Run: `pytest tests/test_program_name_uniqueness.py -q`

Expected: PASS。

### Task 3: 完整性检查与交付准备

**Files:**
- Verify: `backend/app/services/program_service.py`
- Verify: `backend/tests/test_program_name_uniqueness.py`

**Step 1: 搜索旧错误文案**

Run: `rg -n -F "Program name already exists in this parent scope" backend`

Expected: 无匹配结果。

**Step 2: 检查改动范围**

Run: `git diff --check; git diff -- backend/app/services/program_service.py backend/tests/test_program_name_uniqueness.py`

Expected: 无空白错误，且只有三处服务文案及相应测试断言变化。

**Step 3: 准备提交（需要主上确认后执行）**

```bash
git add backend/app/services/program_service.py backend/tests/test_program_name_uniqueness.py
git commit -m "fix: localize program duplicate name error"
```
