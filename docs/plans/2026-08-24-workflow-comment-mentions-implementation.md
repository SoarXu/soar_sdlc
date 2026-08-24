# Workflow Comment Mentions Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rename work-item workflow “补充信息” actions to “评论” and make their dialogs support `@` mentions with existing comment notifications.

**Architecture:** Retain the `add_information` action key as the compatibility contract, while changing its display name. Extract the current detail-comment editor into a shared composer component and use it both in the detail comment panel and workflow action dialog. The composer loads project-scoped eligible mention users from the comment API so the UI matches server validation. Persisted definition names are updated through an idempotent Alembic data migration limited to requirement/task/Bug workflow definitions.

**Tech Stack:** Vue 3, Element Plus, JavaScript ES modules, FastAPI, SQLAlchemy, Alembic, pytest.

---

### Task 1: Write failing display-name and migration tests

**Files:**
- Create: `backend/tests/test_workflow_comment_action_rename_migration.py`
- Modify: `backend/tests/test_default_workflow_templates_api.py`

**Step 1: Add the desired contract**

Require every default requirement/task/Bug transition with `action_key == "add_information"` to have `action_name == "评论"`. Add a migration test that loads `20260824_003_rename_workflow_add_information_to_comment.py`, checks its revision chain, and executes `upgrade()` twice against a temporary schema. Assert only target work-item definitions with `add_information` change; project and other actions remain unchanged.

**Step 2: Verify RED**

```powershell
Set-Location backend
& E:\miniforge3\python.exe -m pytest tests/test_default_workflow_templates_api.py -k add_information tests/test_workflow_comment_action_rename_migration.py -q
```

Expected: fail because templates still expose “补充信息” and no migration exists.

### Task 2: Implement workflow display-name migration

**Files:**
- Modify: `backend/app/services/default_workflow_template_service.py`
- Create: `backend/alembic/versions/20260824_003_rename_workflow_add_information_to_comment.py`

**Step 1: Change template labels**

For the helper calls that create `add_information` transitions in requirement, task and Bug graphs, use action name `评论`. Preserve the key and `command_type="add_information"`.

**Step 2: Add the data migration**

Update `workflow_transitions.action_name` from “补充信息” to “评论” only when the action key equals `add_information`, the owning definition type is requirement, task or Bug, and its source state has no other enabled “评论” action. Keep downgrade non-destructive to avoid overwriting pre-existing custom “评论” action names.

**Step 3: Verify GREEN**

Run the Task 1 command. The focused tests pass.

### Task 3: Extract a reusable mention-capable comment composer

**Files:**
- Create: `frontend/src/components/WorkItemCommentComposer.vue`
- Modify: `frontend/src/components/WorkItemCommentPanel.vue`
- Modify: `frontend/src/api/workItemComments.js`
- Modify: `backend/app/controllers/work_item_comment_controller.py`
- Modify: `backend/app/services/work_item_comment_service.py`
- Modify: `backend/app/views/work_item_comment_view.py`
- Create: `frontend/src/components/workItemCommentComposer.test.mjs`
- Modify: `backend/tests/test_work_item_comment_api.py`

**Step 1: Write the failing component contract test**

Require the new composer to expose a textarea, project-scoped `@` candidate filtering, multi-select mention control, and a `submit` event containing both comment body and mentioned user IDs. Require the detail panel to use it and pass resulting IDs to `createWorkItemComment`. Require the candidate endpoint to exclude non-project members.

**Step 2: Verify RED**

```powershell
Set-Location frontend
node src/components/workItemCommentComposer.test.mjs
```

Expected: fail because the component does not exist.

**Step 3: Implement the shared composer**

Move the existing detail-panel draft, cursor, mention parsing and insertion behavior into the component. Preserve manual mention selection and input filtering. The component loads its own project-member candidate list but must not submit comment API calls itself.

**Step 4: Verify GREEN**

Run the focused frontend test. It passes.

### Task 4: Use the composer for workflow comment actions

**Files:**
- Modify: `frontend/src/components/WorkflowActionButtons.vue`
- Modify: `frontend/src/components/workflowActionButtonsBehavior.test.mjs`

**Step 1: Write the failing contract assertion**

Require workflow comment actions to render `WorkItemCommentComposer`, submit the emitted mention IDs to `createWorkItemComment`, and display “评论成功”; reject the old hardcoded empty mention array and “补充信息成功”.

**Step 2: Verify RED**

```powershell
Set-Location frontend
node src/components/workflowActionButtonsBehavior.test.mjs
```

Expected: fail because the modal uses a generic textarea and passes `mentioned_user_ids: []`.

**Step 3: Implement the workflow dialog path**

Render the shared composer only for `add_information` command actions. Keep generic action forms unchanged. Capture the composer event, call the existing comment API with its body and user IDs, close the dialog and refresh workflow actions.

**Step 4: Verify GREEN**

Run the workflow action behavior test and the composer test.

### Task 5: Verify persistence and regressions

**Files:**
- Verify only.

**Step 1: Upgrade local database**

```powershell
Set-Location backend
& E:\miniforge3\python.exe -m alembic upgrade head
& E:\miniforge3\python.exe -m alembic heads
& E:\miniforge3\python.exe -m alembic current
```

**Step 2: Run focused backend and frontend tests**

```powershell
Set-Location backend
& E:\miniforge3\python.exe -m pytest tests/test_workflow_comment_action_rename_migration.py tests/test_default_workflow_templates_api.py tests/test_work_item_comment_api.py -q
Set-Location ..\frontend
npm test
npm run build
```

**Step 3: Inspect final diff**

```powershell
Set-Location ..
git diff --check
git status --short
```

Expected: all tests/build checks pass; only intended files are changed.
