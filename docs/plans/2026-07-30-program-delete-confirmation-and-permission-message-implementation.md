# 项目集删除确认与权限提示中文化 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将项目集删除改为居中确认框，并让项目集治理权限拒绝统一显示“无权限”。

**Architecture:** 前端使用 Element Plus 命令式确认框，在用户确认后调用既有删除函数。后端仅替换三个项目集治理权限拒绝路径的 `detail`，保持权限规则与 HTTP 403 不变。

**Tech Stack:** Vue 3、Element Plus、Node.js `assert`、Python、FastAPI、pytest。

### Task 1: 锁定前端删除确认契约

**Files:**
- Modify: `frontend/src/views/ProgramsView.vue`
- Test: `frontend/src/views/programOwnerPermission.test.mjs`

**Step 1: 写入失败断言**

断言页面导入 `ElMessageBox`、删除按钮调用确认函数、不再出现 `el-popconfirm`，且确认后调用删除函数。

**Step 2: 验证红灯**

Run: `node src/views/programOwnerPermission.test.mjs`

Expected: FAIL，旧实现不包含模态确认。

**Step 3: 最小化实现**

将删除按钮改为调用 `confirmRemoveProgram`，使用 `ElMessageBox.confirm` 提示级联删除风险；确认后调用 `removeProgram`，取消时不执行删除。

**Step 4: 验证绿灯**

Run: `node src/views/programOwnerPermission.test.mjs`

Expected: PASS。

### Task 2: 锁定治理权限错误契约

**Files:**
- Modify: `backend/app/services/program_service.py`
- Create: `backend/tests/test_program_permission_messages.py`

**Step 1: 写入失败单元测试**

用替身权限检查覆盖删除、管理和新建子项目集三个拒绝路径，断言均为 HTTP 403 和“无权限”。

**Step 2: 验证红灯**

Run: `pytest tests/test_program_permission_messages.py -q`

Expected: FAIL，旧实现返回英文错误详情。

**Step 3: 最小化实现**

将三处 `Program governance permission required` 改为“无权限”。

**Step 4: 验证绿灯**

Run: `pytest tests/test_program_permission_messages.py -q`

Expected: PASS。

### Task 3: 完整性检查

**Step 1:** 运行前端契约测试与后端单元测试。

**Step 2:** 运行 `npm run build`，确认前端可构建。

**Step 3:** 搜索遗留 `el-popconfirm` 和英文治理权限文案，并运行 `git diff --check`。

**Step 4:** 得到主上确认后再提交、推送或合并。
