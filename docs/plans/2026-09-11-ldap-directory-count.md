# LDAP Directory Count Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在 LDAP 用户列表中显示当前查询条件下的总记录数、总页数和当前页，并在 AD 未返回估算总数时明确显示总数未知。

**Architecture:** 从 ldap3 分页响应控制中读取 AD 返回的估算总数，沿现有 `LdapSearchResult` 和目录 API 透传 `total`。前端根据 `total` 与每页数量计算总页数，游标翻页仍由现有 next_cursor/back stack 驱动。

**Tech Stack:** FastAPI、ldap3、Vue 3、Element Plus、Node.js source-contract tests。

---

### Task 1: Extend LDAP result with directory total

**Files:**
- Modify: `backend/app/services/ldap_client.py`
- Test: `backend/tests/test_ldap_client.py`

1. Add a failing test asserting the paged-results control's `size` becomes `LdapSearchResult.total`.
2. Run the focused test and confirm it fails because the result has no total field.
3. Add nullable `total` to `LdapSearchResult` and extract a non-negative integer from the paged control.
4. Run the focused LDAP client tests.

### Task 2: Return total from directory API

**Files:**
- Modify: `backend/app/services/ldap_config_service.py`
- Test: `backend/tests/test_ldap_directory_api.py`

1. Add a failing API test expecting `total` in the directory response.
2. Run the focused test and confirm the response is missing `total`.
3. Pass `result.total` through the service response.
4. Run the LDAP directory API tests.

### Task 3: Display count and page summary in LDAP view

**Files:**
- Modify: `frontend/src/views/LdapIntegrationView.vue`
- Test: `frontend/src/views/ldapIntegrationView.test.mjs`

1. Add source-contract assertions for total state, total-page calculation, and Chinese summary text.
2. Run the focused frontend test and confirm it fails.
3. Track `directoryTotal`, update it from API responses, calculate total pages, and render `共 X 条 / 第 Y / Z 页`; render `总数未知` when total is null.
4. Reset the total on a new query only when the API response has no total, preserving the current response value during cursor navigation.
5. Run all frontend tests and production build.

### Task 4: Verify and deliver

1. Run backend LDAP tests, frontend tests, production build, and `git diff --check`.
2. Review the diff and stage only LDAP-related files.
3. Commit and push only after explicit delivery confirmation.
