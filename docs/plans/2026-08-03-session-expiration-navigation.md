# Session Expiration Navigation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redirect to login after the session-expiration message closes, without allowing page-level unsaved guards to block the redirect.

**Architecture:** Keep `createSessionExpirationHandler` responsible for ordering storage cleanup, notification completion, and navigation. In the HTTP adapter, make the Element Plus `onClose` callback resolve the notification Promise and resolve the login route to a browser-level `location.replace` destination.

**Tech Stack:** Vue 3, Axios, Element Plus, Vue Router, Node source-contract tests.

### Task 1: Specify notification-before-navigation ordering

**Files:**
- Modify: `frontend/src/utils/sessionExpiration.test.mjs`
- Test: `frontend/src/utils/sessionExpiration.test.mjs`

**Step 1: Write the failing test**

Add a deferred notification scenario. Assert that session storage is cleared immediately, navigation has not occurred before the notification resolves, and navigation occurs exactly once after it resolves.

**Step 2: Run test to verify it fails**

Run: `npm test -- sessionexpiration`

Expected: FAIL because the current HTTP adapter passes a synchronous Element Plus message result instead of a completion Promise.

### Task 2: Await actual message closure and bypass route guards

**Files:**
- Modify: `frontend/src/api/http.js:16-24`
- Modify: `frontend/src/api/http.test.mjs`
- Test: `frontend/src/api/http.test.mjs`

**Step 1: Write the failing source contract**

Assert that HTTP notification config uses `onClose` and that navigation resolves the login location through `window.location.replace` instead of `router.replace`.

**Step 2: Write minimal implementation**

Wrap `ElMessage.warning` in a Promise resolved by `onClose`. Resolve the login location with the router and call browser `replace` after notification closure. Keep the handler's existing request deduplication and login-request exclusion.

**Step 3: Run tests to verify they pass**

Run: `npm test -- sessionexpiration http`

Expected: PASS.

### Task 3: Verify frontend behavior

**Files:**
- Verify only.

**Step 1: Run full tests and production build**

Run: `npm test`

Run: `npm run build`

**Step 2: Inspect whitespace**

Run: `git diff --check`
