# 需求任务迭代同步 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 保持需求与其关联任务的迭代归属一致，使迭代结束校验完整统计需求子任务。

**Architecture:** 普通任务创建时从需求继承迭代归属。需求关联、解绑与延期使用同一任务同步辅助函数，并复用既有 `move_work_item_to_iteration` 写入成员关系历史；直接任务不参与同步。

**Tech Stack:** FastAPI, SQLAlchemy, pytest。

---

### Task 1: 普通任务创建继承需求迭代

**Files:**
- Modify: `backend/tests/test_requirement_task_api.py`
- Modify: `backend/app/services/task_service.py:68-102`

**Step 1: Write the failing test**

在 `test_requirement_and_task_create_default_to_template_statuses_and_prd_fields` 后增加测试：创建已关联交付迭代的需求，再通过 `POST /api/v1/tasks` 创建带 `requirement_id` 的任务；断言任务的 `iteration_id` 等于需求的迭代，并存在任务迭代历史。

**Step 2: Run test to verify it fails**

Run: `pytest backend/tests/test_requirement_task_api.py -q`

Expected: 新任务的 `iteration_id` 为 `None`，断言失败。

**Step 3: Write minimal implementation**

在 `create_task` 中读取有效需求；当请求携带 `requirement_id` 时将 `data["iteration_id"]` 设为该需求的 `iteration_id`，再执行现有可变性、范围校验和历史记录流程。

**Step 4: Run test to verify it passes**

Run: `pytest backend/tests/test_requirement_task_api.py -q`

Expected: PASS。

### Task 2: 需求迭代变更同步关联任务

**Files:**
- Modify: `backend/tests/test_iteration_detail_api.py`
- Modify: `backend/app/services/iteration_service.py:119-153, 242-295, 622-664`
- Modify: `backend/app/services/workflow_runtime_service.py:1641-1674`

**Step 1: Write the failing tests**

新增三个独立测试：

1. `link_requirements` 将需求及其关联任务同步到交付迭代，结束迭代阻断明细的任务计数包含该任务。
2. `unlink_requirement` 将需求移回需求池时，关联任务的 `iteration_id` 变为 `None`。
3. `defer_work_items` 延期需求时，关联任务同步到目标迭代。

**Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_iteration_detail_api.py -q`

Expected: 关联任务仍为 `None` 或停留源迭代，新增断言失败。

**Step 3: Write minimal implementation**

新增私有辅助函数，锁定并查询指定需求的未删除关联任务，逐个调用 `move_work_item_to_iteration`。在 `link_requirements`、`unlink_requirement` 和 `defer_work_items` 的需求操作后调用该函数。结束迭代校验维持直接按 `iteration_id` 查询，因此同步后的任务自然进入阻断明细。

**Step 4: Run tests to verify they pass**

Run: `pytest backend/tests/test_iteration_detail_api.py -q`

Expected: PASS。

### Task 3: 工作台终态标题不使用删除线

**Files:**
- Modify: `frontend/src/styles.css:1217-1224`
- Test: `frontend/src/utils/workbenchViewModel.test.mjs`

**Step 1: Write the failing test**

读取 `styles.css`，断言 `.workbench-title-button.is-terminal` 样式块不存在
`text-decoration: line-through`。

**Step 2: Run test to verify it fails**

Run: `npm test -- workbenchViewModel.test.mjs`

Expected: 断言因现有删除线样式失败。

**Step 3: Write minimal implementation**

删除 `.workbench-title-button.is-terminal` 中的三条 `text-decoration` 声明，保留
终态标题颜色。

**Step 4: Run test to verify it passes**

Run: `npm test -- workbenchViewModel.test.mjs`

Expected: PASS。

### Task 4: 完整回归验证

**Files:**
- Verify: `backend/tests/test_requirement_task_api.py`
- Verify: `backend/tests/test_iteration_detail_api.py`
- Verify: `backend/tests/test_linked_task_api.py`

**Step 1: Run focused regression**

Run: `pytest backend/tests/test_requirement_task_api.py backend/tests/test_iteration_detail_api.py backend/tests/test_linked_task_api.py -q`

Expected: PASS。

**Step 2: Run repository validation**

Run: `git diff --check`

Expected: no output and exit code 0。

**Step 3: Inspect changes**

Run: `git diff -- backend/app/services/task_service.py backend/app/services/iteration_service.py backend/tests/test_requirement_task_api.py backend/tests/test_iteration_detail_api.py`

Expected: 仅包含需求与关联任务迭代同步及其测试。
