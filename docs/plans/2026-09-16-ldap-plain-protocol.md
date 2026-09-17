# LDAP Plain Protocol Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an explicit unencrypted LDAP protocol option without changing existing StartTLS or LDAPS configurations.

**Architecture:** Persist `plain` as a third protocol value alongside the existing `ldap` and `ldaps` values. Both directory queries and LDAP user authentication branch on the same protocol semantics, while the frontend exposes the three choices and maps their conventional ports.

**Tech Stack:** FastAPI, Pydantic, ldap3, pytest, Vue 3, Element Plus, Node test runner

---

### Task 1: Accept the plain protocol in the configuration API

**Files:**
- Modify: `backend/app/views/ldap_view.py:11`
- Test: `backend/tests/test_ldap_config_api.py`

**Step 1: Write the failing test**

Add an API test that saves `_payload(protocol="plain", port=389)` and asserts a 200 response with `protocol == "plain"` and `port == 389`.

**Step 2: Run the test to verify it fails**

Run from `backend/`:

```sh
pytest tests/test_ldap_config_api.py -q
```

Expected: the new test fails with a request validation error because `plain` is not in the protocol literal.

**Step 3: Write the minimal implementation**

Change the write model to:

```python
protocol: Literal["plain", "ldap", "ldaps"] = "ldaps"
```

Do not change the database schema; `plain` fits the existing `VARCHAR(8)` column.

**Step 4: Run the test to verify it passes**

```sh
pytest tests/test_ldap_config_api.py -q
```

Expected: all tests in the file pass.

**Step 5: Delivery checkpoint**

Do not commit without the user's explicit delivery choice.

### Task 2: Implement plain directory connections

**Files:**
- Modify: `backend/app/services/ldap_client.py:151-176`
- Test: `backend/tests/test_ldap_client.py`

**Step 1: Write the failing test**

Add a test using `config.protocol = "plain"` that records connection calls and expects:

```python
["connection", "open", "bind"]
```

Assert `use_ssl is False`, `auto_bind is False`, and that `start_tls` is never called.

**Step 2: Run the test to verify it fails**

```sh
pytest tests/test_ldap_client.py -q
```

Expected: the new test fails because the current implementation returns without opening or binding for `plain`.

**Step 3: Write the minimal implementation**

Create TLS settings only for `ldap` and `ldaps`. For both `plain` and `ldap`, explicitly open the connection; call `start_tls()` only for `ldap`; then bind. Preserve existing network, TLS, and bind error mapping.

**Step 4: Run the test to verify it passes**

```sh
pytest tests/test_ldap_client.py -q
```

Expected: plain, StartTLS, LDAPS, query, and error-mapping tests all pass.

**Step 5: Delivery checkpoint**

Do not commit without the user's explicit delivery choice.

### Task 3: Implement plain LDAP user authentication

**Files:**
- Modify: `backend/app/services/ldap_auth_service.py:53-76`
- Test: `backend/tests/test_ldap_auth.py`

**Step 1: Write the failing test**

Add a `protocol="plain"` authentication test that expects `open()` followed by `bind()`, verifies `use_ssl=False` and `auto_bind=False`, and provides a `start_tls()` method that fails the test if called.

**Step 2: Run the test to verify it fails**

```sh
pytest tests/test_ldap_auth.py -q
```

Expected: the new test fails because the current implementation does not explicitly bind for `plain`.

**Step 3: Write the minimal implementation**

Mirror the directory client protocol branches: `plain` opens and binds directly, `ldap` opens then upgrades and binds, and `ldaps` retains SSL auto-bind.

**Step 4: Run the test to verify it passes**

```sh
pytest tests/test_ldap_auth.py -q
```

Expected: all LDAP authentication tests pass.

**Step 5: Delivery checkpoint**

Do not commit without the user's explicit delivery choice.

### Task 4: Expose all three protocol choices in the frontend

**Files:**
- Modify: `frontend/src/views/LdapIntegrationView.vue:107-120`
- Test: `frontend/src/views/ldapIntegrationView.test.mjs`

**Step 1: Write the failing test**

Add a source contract test asserting the three label/value pairs and a port handler that treats both `plain` and `ldap` as port 389 while retaining LDAPS port 636.

**Step 2: Run the test to verify it fails**

Run from `frontend/`:

```sh
npm test -- src/views/ldapIntegrationView.test.mjs
```

Expected: the new test fails because `plain` is not present.

**Step 3: Write the minimal implementation**

Set the options to:

```javascript
[
  { label: 'LDAP（不加密）', value: 'plain' },
  { label: 'LDAP + StartTLS', value: 'ldap' },
  { label: 'LDAPS', value: 'ldaps' },
]
```

Update `handleProtocolChange` so `plain` and `ldap` map 636 to 389, while `ldaps` maps 389 to 636. Keep the default as `ldaps`/636.

**Step 4: Run the test and build**

```sh
npm test
npm run build
```

Expected: all frontend tests pass and the production build exits successfully.

**Step 5: Delivery checkpoint**

Do not commit without the user's explicit delivery choice.

### Task 5: Run focused and regression verification

**Files:**
- Verify only; no planned production edits

**Step 1: Run focused backend tests**

```sh
pytest tests/test_ldap_config_api.py tests/test_ldap_client.py tests/test_ldap_auth.py -q
```

Expected: all focused backend tests pass.

**Step 2: Run the broader LDAP backend suite**

```sh
pytest tests/test_ldap_*.py -q
```

Expected: all LDAP tests pass.

**Step 3: Re-run frontend verification**

```sh
npm test
npm run build
```

Expected: all frontend tests pass and the build succeeds.

**Step 4: Inspect the diff and repository delivery state**

Run `git diff --check`, inspect only LDAP-related diffs, and query the current branch, local main branch, remotes, and upstream before offering delivery options. Preserve all unrelated user changes.

**Step 5: Delivery checkpoint**

Report implementation and verification results, then ask the user to choose a Git delivery action. Do not commit, push, create a PR, or merge without explicit confirmation.
