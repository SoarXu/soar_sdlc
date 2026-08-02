# Program Owner Delete Tree Implementation Plan

**Goal:** 允许项目集负责人删除满足安全条件的项目集树。

### Task 1: 编写失败测试

在 `backend/tests/test_program_permission_service.py` 增加负责人删除已关闭、项目终态的非空树测试；断言 `can_delete_program` 返回真。

### Task 2: 最小权限调整

修改 `backend/app/services/program_permission_service.py`，让已通过治理权校验的负责人复用现有树关闭与项目终态检查。

### Task 3: 验证

运行 `pytest backend/tests/test_program_permission_service.py -q` 与 `git diff --check`。
