# LDAP Manual User Binding Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 允许管理员将 AD 用户手动绑定到现有 SDLC 用户，保留原用户 ID、项目关系、权限和历史快照，并切换为 AD 登录。

**Architecture:** 复用现有 LDAP 同步事务和用户主键，不迁移项目成员或负责人引用。新增明确的手动绑定请求语义，后端重新校验 AD 身份唯一性、目标用户状态和账号/工号唯一约束；前端在 AD 列表行提供绑定操作并选择有效 SDLC 用户。

**Tech Stack:** FastAPI、SQLAlchemy、Vue 3、Element Plus、Node.js source-contract tests。

---

### Task 1: Permit explicit manual bind targets

**Files:**
- Modify: `backend/app/services/ldap_sync_service.py`
- Test: `backend/tests/test_ldap_sync_api.py`

1. Add a failing test where the AD entry does not produce an automatic match but an administrator explicitly supplies a local user ID.
2. Run the focused test and confirm the current `BIND_NOT_SUGGESTED` rejection.
3. Allow explicit bind targets when the target is active, un-deleted, unbound, and the directory entry is enabled; retain all conflict checks and update only the existing user row.
4. Add tests for already-bound target and username/employee uniqueness conflicts.

### Task 2: Add user selection endpoint contract

**Files:**
- Modify: `backend/app/controllers/ldap_controller.py`
- Modify: `backend/app/services/ldap_config_service.py`
- Modify: `backend/app/views/ldap_view.py`
- Test: `backend/tests/test_ldap_sync_api.py`

1. Add a system-admin LDAP endpoint returning active SDLC users safe for binding.
2. Exclude deleted users and expose only ID, username, full name, employee number, and auth source.
3. Add permission tests.

### Task 3: Add manual bind UI

**Files:**
- Modify: `frontend/src/api/ldap.js`
- Modify: `frontend/src/views/LdapIntegrationView.vue`
- Test: `frontend/src/views/ldapIntegrationView.test.mjs`

1. Add source-contract tests for the row action, selection dialog, user search, explicit bind request, and refresh.
2. Add a “绑定 SDLC 用户” action for eligible AD rows.
3. Load SDLC users when the dialog opens, filter by name/account/employee number, confirm the target, and submit a bind decision.
4. Preserve existing batch sync behavior and display backend conflict messages.

### Task 4: Verify and deliver

1. Run LDAP backend tests where the MySQL test database is available, frontend tests, production build, and diff checks.
2. Review and stage only LDAP-related files.
3. Commit and push only after explicit delivery confirmation.
