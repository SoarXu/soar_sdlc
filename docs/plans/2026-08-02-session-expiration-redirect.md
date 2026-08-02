# Session Expiration Redirect Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Redirect users to login after a protected API request reports that their session is no longer authenticated.

**Architecture:** Keep 401 handling in the shared Axios response-error interceptor so every API consumer gets identical session cleanup, Chinese feedback, and navigation. Extract the side-effect orchestration into a small utility with injected browser and UI dependencies so it remains testable with the repository's Node test runner.

**Tech Stack:** Vue 3, Vue Router, Pinia session storage, Axios, Element Plus, Node `assert` tests.

### Task 1: Cover session-expiration behavior

**Files:**
- Create: `frontend/src/utils/sessionExpiration.test.mjs`
- Create: `frontend/src/utils/sessionExpiration.js`

**Step 1: Write the failing test**

Test that a protected 401 removes all six session keys, displays `登录状态已失效，请重新登录`, and navigates to the login route with a redirect query. Test that a login endpoint 401 is ignored and that a second protected 401 while the first notice is pending does not repeat side effects.

**Step 2: Run the test to verify it fails**

Run: `npm test -- sessionexpiration`

Expected: FAIL because `sessionExpiration.js` does not exist.

**Step 3: Implement the minimal utility**

Export an async handler that accepts the request URL and injectable storage, notifier, navigator, and current-path provider. It should ignore auth endpoints, deduplicate an in-progress expiration flow, remove the auth-store keys, await the Chinese notice, and navigate once.

**Step 4: Run the test to verify it passes**

Run: `npm test -- sessionexpiration`

Expected: exit code 0.

### Task 2: Connect the utility to Axios

**Files:**
- Modify: `frontend/src/api/http.js`
- Test: `frontend/src/api/http.test.mjs`

**Step 1: Write the failing integration test**

Verify the response-error interceptor invokes the shared handler only for a response whose status is 401, preserving other errors as rejected promises.

**Step 2: Run the test to verify it fails**

Run: `npm test -- http`

Expected: FAIL because no response-error interceptor exists.

**Step 3: Implement the minimal interceptor**

Register an Axios response-error interceptor that delegates 401 responses to the session-expiration utility, then rethrows the original error for callers' existing control flow.

**Step 4: Run focused tests**

Run: `npm test -- sessionexpiration http`

Expected: exit code 0.

### Task 3: Verify regression safety

**Files:**
- Modify: no additional files expected

**Step 1: Run the full frontend suite**

Run: `npm test`

Expected: exit code 0 and no test failures.

**Step 2: Build the production bundle**

Run: `npm run build`

Expected: Vite build completes with exit code 0.

**Step 3: Manually verify the request path**

With the app running, clear `access_token` or use an expired token, open a protected page, and confirm the Chinese notice appears once before navigation to `/login`.

**Step 4: Commit**

Do not commit automatically. Present the verified local changes and obtain the requested delivery confirmation before any Git operation.
