# 迭代启动层级同步 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 启动交付迭代时，在一个事务内同步启动关联项目及其项目集祖先，并拒绝任何已关闭父级。

**Architecture:** 在工作流运行时处理迭代 `start` 前，解析并锁定迭代关联项目及项目集树，先完成关闭状态和可执行项目启动动作校验。通过现有项目工作流状态、状态操作与项目集激活规则复用生命周期语义；所有同步步骤使用同一事务，避免部分成功。

**Tech Stack:** Python、FastAPI、SQLAlchemy、Pytest。

---

### Task 1: 为迭代启动层级同步建立失败回归测试

**Files:**
- Modify: `backend/tests/test_iteration_detail_api.py`
- Verify: `backend/app/services/workflow_runtime_service.py`

**Step 1: Write the failing tests**

新增以下 API 场景：

1. 创建规划中的父项目集、子项目集、关联到子项目集的规划中项目和交付迭代；通过 `/api/v1/workflow-runtime/iteration/{id}/transition` 执行 `start`。断言迭代和项目进入进行中，两个项目集进入进行中，三者的空实际开始日期都使用请求的 `effective_time` 日期。
2. 创建关联两个规划中项目的交付迭代；断言一次启动同步两个项目及各自项目集。
3. 关闭任一关联项目或项目集后启动迭代；断言响应为 4xx，迭代、其他关联项目和项目集均保持原状态。

**Step 2: Run tests to verify they fail**

Run: `pytest backend/tests/test_iteration_detail_api.py -k "iteration_start and hierarchy" -q`

Expected: FAIL，当前运行时仅更新迭代，不会同步关联项目和项目集，也不会拒绝关闭父级。

### Task 2: 实现迭代启动前的层级校验与同步

**Files:**
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/services/project_service.py`
- Verify: `backend/app/services/program_service.py`

**Step 1: Add hierarchy resolution helpers**

在工作流运行时新增内部辅助函数，读取 `IterationProject` 关联项目，锁定项目及其 `Program` 祖先，并返回去重后的稳定顺序集合。辅助函数检测项目工作流终态、项目集 `closed` 状态和缺失的 `start` 流转，发现任一异常即抛出明确的 `HTTPException`。

**Step 2: Run the focused tests to verify they still fail**

Run: `pytest backend/tests/test_iteration_detail_api.py -k "iteration_start and hierarchy" -q`

Expected: FAIL，辅助函数尚未接入迭代运行时流程。

**Step 3: Integrate the single transaction**

在迭代 `start` 的通用运行时路径中，在提交前：

1. 使用迭代请求的 `effective_time` 解析并校验父级集合；
2. 对规划中关联项目执行当前定义的 `start` 状态流转并记录原操作人及“迭代启动同步”来源；
3. 复用项目集激活逻辑同步项目集祖先与空开始日期；
4. 最后写入迭代的开始状态和状态操作。

所有内部项目流转使用 `commit=False`，由外层迭代运行时一次提交；任一异常触发回滚。

**Step 4: Run focused tests to verify they pass**

Run: `pytest backend/tests/test_iteration_detail_api.py -k "iteration_start and hierarchy" -q`

Expected: PASS，成功启动场景层级状态一致，失败场景无部分更新。

### Task 3: 执行回归验证

**Files:**
- Verify: `backend/tests/test_iteration_detail_api.py`
- Verify: `backend/tests/test_program_project_api.py`
- Verify: `backend/tests/test_workflow_runtime_api.py`

**Step 1: Run affected backend suites**

Run: `pytest backend/tests/test_iteration_detail_api.py backend/tests/test_program_project_api.py backend/tests/test_workflow_runtime_api.py -q`

Expected: PASS，迭代、项目、项目集和运行时流转测试全部通过。

**Step 2: Check the final diff**

Run: `git diff --check`

Expected: PASS，无空白错误。

**Step 3: Defer Git delivery**

不执行暂存、提交、推送、创建 PR 或合并；实现完成后由主上选择交付方式。
