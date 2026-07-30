# Program Owner Permission Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement inherited program-owner governance authority without
changing workflow assignment or workflow-transition authorization.

**Architecture:** Add a focused program permission service that resolves
ownership through the active program ancestor chain. Program endpoints use the
service directly; project governance checks extend the existing project
permission service with program-derived authority. Permissions stay dynamic,
so project-member rows are never copied or synchronized.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Pytest, Vue 3, Element Plus,
Node source tests.

---

### Task 1: Specify the program permission contract with failing tests

**Files:**
- Create: `backend/tests/test_program_permission_service.py`
- Modify: `backend/tests/test_program_project_api.py`

**Step 1: Write unit tests for authority resolution**

Cover the following cases with a program root, child, grandchild, and project:

- a program owner manages the owned program and all descendants;
- a child owner does not manage the parent or sibling;
- a system administrator manages every program;
- an owner transfer removes the former owner's derived authority;
- deleted programs do not confer inherited authority.

**Step 2: Write API tests for the approved rules**

Add authenticated requests proving that any active user creates a root program,
omitting `owner_id` assigns the creator, an ancestor owner creates a child,
and an unrelated user receives HTTP 403 for child creation, update, lifecycle,
and ownership transfer.

**Step 3: Run the focused tests to verify failure**

Run: `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests/test_program_permission_service.py backend/tests/test_program_project_api.py -q`

Expected: FAIL because program-owner authority has not been implemented.

### Task 2: Add dynamic program ownership resolution

**Files:**
- Create: `backend/app/services/program_permission_service.py`
- Test: `backend/tests/test_program_permission_service.py`

**Step 1: Implement the smallest query helpers**

Add helpers that accept a session, target program or project ID, and actor ID:

- `is_program_governor`: return true for a system administrator or for a
  matching `owner_id` while walking from the active target program to its
  active ancestors;
- `can_create_child_program`: require `is_program_governor` on the parent;
- `can_manage_program`: require authenticated program governance;
- `can_delete_program`: allow a governor only when the program is empty; allow
  an administrator to remove a tree only when every affected program and
  project is closed.

Stop traversal and deny authority if the requested program is missing or
deleted. Guard against corrupted parent cycles by tracking visited IDs and
raising a domain error rather than looping indefinitely.

**Step 2: Run the unit tests**

Run: `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests/test_program_permission_service.py -q`

Expected: PASS.

### Task 3: Enforce program endpoint permissions and owner defaults

**Files:**
- Modify: `backend/app/controllers/program_controller.py`
- Modify: `backend/app/services/program_service.py`
- Modify: `backend/app/views/program_view.py`
- Test: `backend/tests/test_program_project_api.py`

**Step 1: Require authentication instead of system-administrator role for creation**

Use `get_current_user` for `POST /programs`. Pass the actor to
`create_program`; default a missing `owner_id` to `actor.id` and reject a
deleted or inactive explicit owner.

**Step 2: Apply governance checks consistently**

Before a child creation, verify authority on `parent_id`. Before update,
status changes, and owner transfer, verify authority on the target program.
Retain read-only behavior unless a separately approved visibility policy is
introduced.

**Step 3: Replace recursive owner deletion behavior**

For a non-administrator, reject deletion unless the target program has no
active child programs or projects. For an administrator, preserve the existing
soft-delete tree behavior only after verifying that all affected nodes are
closed.

**Step 4: Run the program API tests**

Run: `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests/test_program_project_api.py -q`

Expected: PASS.

### Task 4: Extend project governance, without touching work-item workflow

**Files:**
- Modify: `backend/app/services/project_permission_service.py`
- Test: `backend/tests/test_program_permission_service.py`
- Test: `backend/tests/test_program_project_api.py`

**Step 1: Extend only project-governance predicates**

Make `can_manage_project` return true for an inherited program governor. This
enables descendant project metadata, membership, and lifecycle management.
Keep `can_create_work_item`, `can_delete_work_item`,
`ensure_work_item_action_permission`, and workflow role resolution unchanged.

**Step 2: Add regression tests**

Verify that a program owner can update a descendant project and replace its
members, but cannot directly update a requirement, task, or bug merely from
program ownership.

**Step 3: Run focused backend tests**

Run: `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests/test_program_permission_service.py backend/tests/test_program_project_api.py backend/tests/test_requirement_api.py backend/tests/test_task_api.py backend/tests/test_bug_api.py -q`

Expected: PASS.

### Task 5: Reflect server-authoritative permissions in the program UI

**Files:**
- Modify: `frontend/src/views/ProgramsView.vue`
- Modify: `frontend/src/api/programs.js` only if the API response needs an
  explicit capability field
- Create: `frontend/src/views/programOwnerPermission.test.mjs`

**Step 1: Write source and interaction tests**

Assert that a new program form initializes the owner selector from the current
user, keeps it editable, and does not imply that the owner is a work-item
handler. Assert that unauthorized API responses produce the existing error
feedback and refresh server state.

**Step 2: Implement the minimal UI changes**

Prefill owner from the authenticated user for a new program. Preserve the
existing user selector for owner transfer. Render program actions according to
server-provided capabilities if added; do not duplicate ancestor traversal in
the browser.

**Step 3: Run the frontend tests and build**

Run: `node --test frontend/src/views/programOwnerPermission.test.mjs`

Run: `npm run build`

Expected: both commands exit with status 0.

### Task 6: Full verification and review

**Files:**
- Verify: files changed by Tasks 1-5

**Step 1: Run the backend suite**

Run: `E:\miniconda3\envs\soar_sdlc_py311\python.exe -m pytest backend/tests -q`

Expected: PASS.

**Step 2: Run frontend checks**

Run: `npm test`

Run: `npm run build`

Expected: both commands exit with status 0.

**Step 3: Inspect scope**

Run: `git diff --check` and `git status --short`

Expected: no whitespace errors and no changes outside the permission feature,
its tests, and these approved documents.
