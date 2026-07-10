# Admin Navigation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a new `/admin` overview page and regroup role and workflow pages under a `后台管理` navigation section without breaking the existing routes.

**Architecture:** The change stays entirely in the Vue frontend. A new `AdminView` provides a compact overview page, the router gets a new `/admin` child route, and the existing sidebar menu is restructured so the backend-related pages live under one navigation group while `/roles` and `/workflow` continue to work unchanged.

**Tech Stack:** Vue 3, Vue Router 4, Element Plus, Vite

---

### Task 1: Define admin overview metadata

**Files:**
- Create: `frontend/src/utils/adminModules.js`
- Test: `frontend/src/utils/adminModules.test.mjs`

**Step 1: Write the failing test**

```javascript
import test from 'node:test'
import assert from 'node:assert/strict'

import { adminModules } from './adminModules.js'

test('adminModules exposes the backend entry cards in sidebar order', () => {
  assert.deepEqual(
    adminModules.map((item) => item.path),
    ['/roles', '/workflow']
  )
})
```

**Step 2: Run test to verify it fails**

Run: `node --test frontend/src/utils/adminModules.test.mjs`
Expected: FAIL with a module-not-found error for `adminModules.js`

**Step 3: Write minimal implementation**

```javascript
export const adminModules = [
  {
    key: 'roles',
    title: '角色管理',
    description: '维护业务角色，并给用户分配角色。',
    path: '/roles'
  },
  {
    key: 'workflow',
    title: '工作流配置',
    description: '维护工作流方案和项目绑定关系。',
    path: '/workflow'
  }
]
```

**Step 4: Run test to verify it passes**

Run: `node --test frontend/src/utils/adminModules.test.mjs`
Expected: PASS

**Step 5: Commit**

```bash
git add frontend/src/utils/adminModules.js frontend/src/utils/adminModules.test.mjs
git commit -m "test: add admin module metadata"
```

### Task 2: Add the `/admin` overview page

**Files:**
- Create: `frontend/src/views/AdminView.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/styles.css`

**Step 1: Write the failing test**

Create a lightweight assertion in `frontend/src/utils/adminModules.test.mjs` that verifies the metadata includes both card labels used by the overview page.

```javascript
test('adminModules provides titles for the overview cards', () => {
  assert.deepEqual(
    adminModules.map((item) => item.title),
    ['角色管理', '工作流配置']
  )
})
```

**Step 2: Run test to verify it fails**

Run: `node --test frontend/src/utils/adminModules.test.mjs`
Expected: FAIL until the metadata is updated with the required titles

**Step 3: Write minimal implementation**

Implement `AdminView.vue` so it:

- renders a `.page-head` section with `后台管理`
- iterates over `adminModules`
- shows two compact cards with title, description, and an `进入` action
- routes to each module path

Add the route:

```javascript
{ path: 'admin', name: 'admin', component: AdminView }
```

Add scoped styles in `styles.css` for:

- constrained admin page width
- responsive grid using `repeat(auto-fit, minmax(240px, 1fr))`
- compact card header and actions

**Step 4: Run verification**

Run: `npm run build`
Expected: build succeeds and includes the new `AdminView`

**Step 5: Commit**

```bash
git add frontend/src/views/AdminView.vue frontend/src/router/index.js frontend/src/styles.css
git commit -m "feat: add admin overview page"
```

### Task 3: Restructure the sidebar menu

**Files:**
- Modify: `frontend/src/layout/MainLayout.vue`
- Modify: `frontend/src/styles.css`
- Reference: `frontend/src/utils/adminModules.js`

**Step 1: Write the failing test**

Add a final assertion in `frontend/src/utils/adminModules.test.mjs` that the sidebar order remains stable for the backend section.

```javascript
test('adminModules keeps backend navigation order stable', () => {
  assert.deepEqual(
    adminModules.map((item) => item.key),
    ['roles', 'workflow']
  )
})
```

**Step 2: Run test to verify it fails**

Run: `node --test frontend/src/utils/adminModules.test.mjs`
Expected: FAIL until the metadata keys are present and ordered correctly

**Step 3: Write minimal implementation**

Update `MainLayout.vue` to:

- add a `后台管理` section in the sidebar
- keep `角色管理` and `工作流配置` visually nested under it
- navigate to `/admin` from the backend entry
- keep the backend section visibly active for `/admin`, `/roles`, and `/workflow`

Update `styles.css` only as needed to keep submenu spacing and mobile layout aligned with the existing navigation style.

**Step 4: Run verification**

Run: `npm run build`
Expected: build succeeds with the new sidebar structure

**Step 5: Commit**

```bash
git add frontend/src/layout/MainLayout.vue frontend/src/styles.css frontend/src/utils/adminModules.test.mjs
git commit -m "feat: group backend navigation"
```

### Task 4: Final verification

**Files:**
- Reference: `frontend/src/layout/MainLayout.vue`
- Reference: `frontend/src/router/index.js`
- Reference: `frontend/src/views/AdminView.vue`
- Reference: `frontend/src/styles.css`

**Step 1: Run focused tests**

Run: `node --test frontend/src/utils/adminModules.test.mjs`
Expected: PASS

**Step 2: Run full frontend build**

Run: `npm run build`
Expected: PASS with Vite production build output

**Step 3: Manual verification**

Run the frontend locally and verify:

- `/admin` shows the two overview cards
- clicking each card routes correctly
- sidebar backend section remains coherent for `/admin`, `/roles`, and `/workflow`
- narrow viewport layout does not overflow

**Step 4: Commit**

```bash
git add frontend/src/layout/MainLayout.vue frontend/src/router/index.js frontend/src/views/AdminView.vue frontend/src/styles.css frontend/src/utils/adminModules.js frontend/src/utils/adminModules.test.mjs
git commit -m "chore: verify admin navigation changes"
```
