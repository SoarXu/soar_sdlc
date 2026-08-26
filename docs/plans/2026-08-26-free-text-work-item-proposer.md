# Free-text Work Item Proposer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace requirement and Bug proposer user identities with optional free-text values across API, import, workflow, workbench, and UI.

**Architecture:** Add a shared `proposer` text contract to requirements and Bugs, migrate existing names before dropping user ID columns, and remove proposer/reporter identity resolution from workflow behavior. Keep `creator_id` as the only system identity for creation ownership and workbench “created by me” behavior.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, Alembic, pytest, Vue 3, Element Plus, Node source-contract tests, Vite.

---

### Task 1: Define failing backend contract and import tests

**Files:**
- Modify: `backend/tests/test_requirement_import_api.py`
- Modify: `backend/tests/test_model_metadata.py`
- Create: `backend/tests/test_work_item_proposer_text_api.py`

**Step 1: Write failing tests**

- Assert requirement and Bug create/update/read APIs accept `proposer: "外部客户 张三"` and return it unchanged.
- Assert model metadata contains nullable string `proposer` columns and no `proposer_id`/`reporter_id` columns.
- Change import fixtures from `proposer_id` to `proposer` and add an Excel row whose “提出人” does not match any user.
- Assert preview reports zero errors for that row and commit stores the exact text.

**Step 2: Verify RED**

Run: `pytest -q tests/test_work_item_proposer_text_api.py tests/test_requirement_import_api.py tests/test_model_metadata.py`

Expected: FAIL because `proposer` is forbidden/missing and import still resolves users.

### Task 2: Implement text persistence and import behavior

**Files:**
- Create: `backend/alembic/versions/20260826_001_work_item_proposer_text.py`
- Modify: `backend/app/models/requirement.py`
- Modify: `backend/app/models/bug.py`
- Modify: `backend/app/views/requirement_view.py`
- Modify: `backend/app/views/bug_view.py`
- Modify: `backend/app/services/requirement_import_service.py`
- Modify: `backend/app/db/schema.py`

**Step 1: Add the migration**

- Add nullable `proposer TEXT` to both tables.
- Backfill via `users.full_name`, falling back to `users.username`.
- Drop `requirements.proposer_id` and `bugs.reporter_id`; downgrade recreates ID columns without attempting lossy reverse mapping.
- Update compatibility schema SQL so workflow columns are not positioned relative to removed columns.

**Step 2: Implement API and import contracts**

- Replace ID fields with `proposer: str | None` in models and Pydantic views.
- Normalize text with Pydantic string constraints or service-level trimming, preserving arbitrary names without user lookup.
- Change `ParsedRequirementRow.proposer_id` to `proposer`.
- Remove `_resolve_user` use for “提出人” while retaining user resolution helpers needed by any unrelated fields.
- Persist `values.get("提出人") or None` on create and update.

**Step 3: Verify GREEN**

Run: `pytest -q tests/test_work_item_proposer_text_api.py tests/test_requirement_import_api.py tests/test_model_metadata.py`

Expected: PASS.

### Task 3: Remove workflow proposer/reporter identities

**Files:**
- Modify: `backend/tests/test_bug_workflow_api.py`
- Modify: `backend/tests/test_workflow_runtime_api.py`
- Modify: `backend/app/services/workflow_definition_service.py`
- Modify: `backend/app/services/default_workflow_template_service.py`
- Modify: `backend/app/services/workflow_runtime_service.py`
- Modify: `backend/app/services/exception_center_service.py`
- Modify: `frontend/src/components/WorkflowDesigner.vue`
- Modify: `frontend/src/components/WorkflowAdvancedConfigDrawer.vue` if it exposes the same identity/source options.

**Step 1: Write/adjust failing workflow tests**

- Assert workflow identity constants and designer options do not include `proposer`, `reporter`, or `bug_reporter`.
- Assert default Bug transitions omit `reporter` while keeping `tester`, `project_member`, and `project_owner` as applicable.
- Assert Bug verifier fallback skips proposer text and reaches project/default tester logic.

**Step 2: Verify RED**

Run: `pytest -q tests/test_bug_workflow_api.py tests/test_workflow_runtime_api.py`

Expected: FAIL on the legacy reporter identity and fallback behavior.

**Step 3: Implement identity removal**

- Remove proposer/reporter from identity and handler-source registries.
- Remove runtime comparisons against removed ID attributes.
- Remove reporter from default Bug transition role lists.
- Delete reporter fallback branches for task confirmation and Bug verification.
- Remove workflow designer labels and values for the deleted identities/sources.

**Step 4: Verify GREEN**

Run: `pytest -q tests/test_bug_workflow_api.py tests/test_workflow_runtime_api.py`

Expected: PASS.

### Task 4: Update generated Bugs and workbench behavior

**Files:**
- Modify: `backend/tests/test_linked_task_api.py`
- Modify: `backend/tests/test_dashboard_workbench_api.py`
- Modify: `backend/app/views/test_case_view.py`
- Modify: `backend/app/controllers/test_case_controller.py`
- Modify: `backend/app/controllers/test_run_controller.py`
- Modify: `backend/app/services/test_case_service.py`
- Modify: `backend/app/services/bug_service.py`
- Modify: `backend/app/services/dashboard_service.py`
- Modify: `backend/app/views/dashboard_view.py`

**Step 1: Write/adjust failing tests**

- Assert Bugs generated from test cases/runs store a proposer display name rather than a user ID.
- Assert workbench “created by me” includes requirements/Bugs through `creator_id` only.
- Assert dashboard view models no longer expose proposer/reporter IDs.

**Step 2: Verify RED**

Run: `pytest -q tests/test_linked_task_api.py tests/test_dashboard_workbench_api.py`

Expected: FAIL because generated Bugs and workbench queries still use reporter/proposer IDs.

**Step 3: Implement behavior**

- Change generated-Bug request fields to optional proposer text.
- Resolve fallback display names from the current user/executor/tester, not as workflow identity.
- Remove proposer/reporter columns from dashboard unions and serializers.
- Simplify “created by me” filtering to `creator_id == user_id`.

**Step 4: Verify GREEN**

Run: `pytest -q tests/test_linked_task_api.py tests/test_dashboard_workbench_api.py`

Expected: PASS.

### Task 5: Convert every frontend form and detail view

**Files:**
- Create: `frontend/src/views/workItemProposerText.test.mjs`
- Modify: `frontend/src/views/RequirementsView.vue`
- Modify: `frontend/src/views/ProjectDetailView.vue`
- Modify: `frontend/src/views/BugsView.vue`
- Modify: `frontend/src/views/IterationDetailView.vue`
- Modify: `frontend/src/views/RequirementDetailView.vue`
- Modify: `frontend/src/views/BugDetailView.vue`
- Modify: `frontend/src/components/work-items/RequirementEditDialog.vue`
- Modify: `frontend/src/components/work-items/BugEditDialog.vue`
- Modify: `frontend/src/utils/auditHistoryLabels.js`

**Step 1: Write the failing source-contract test**

- Load all affected Vue sources.
- Assert each “提出人” control is an `el-input` bound to `.proposer`.
- Assert detail views render `.proposer` directly.
- Assert sources contain no `.proposer_id` or `.reporter_id` bindings.
- Assert audit history treats `proposer` as plain text.

**Step 2: Verify RED**

Run: `node src/views/workItemProposerText.test.mjs`

Expected: FAIL on existing user select bindings.

**Step 3: Implement UI conversion**

- Replace proposer user selects with clearable `el-input` controls and text placeholders.
- Rename reactive fields, resets, edit population, payload construction, and detail rendering to `proposer`.
- Stop defaulting requirement proposer to the logged-in user; leave blank unless entered.
- Remove proposer/reporter from the audit user-field set and add the plain-text history label.

**Step 4: Verify GREEN**

Run: `node src/views/workItemProposerText.test.mjs`

Expected: PASS.

### Task 6: Full regression and migration verification

**Files:**
- Modify tests only if a genuine obsolete expectation remains; do not weaken unrelated assertions.

**Step 1: Run focused backend suite**

Run: `pytest -q tests/test_work_item_proposer_text_api.py tests/test_requirement_import_api.py tests/test_model_metadata.py tests/test_bug_workflow_api.py tests/test_workflow_runtime_api.py tests/test_linked_task_api.py tests/test_dashboard_workbench_api.py`

Expected: PASS with zero failures.

**Step 2: Run full frontend tests and build**

Run: `npm test`

Expected: PASS with zero failures.

Run: `npm run build`

Expected: exit code 0.

**Step 3: Verify stale references**

Run: `rg -n "proposer_id|reporter_id|bug_reporter" backend/app frontend/src`

Expected: no production references, except explicitly retained migration downgrade/history text if required.

**Step 4: Inspect final diff**

Run: `git status --short` and `git diff --check`

Expected: only scoped local changes plus the pre-existing user changes; no whitespace errors.

**Step 5: Stop before Git delivery**

Report modifications and verification results to 主上 and ask which of the five approved delivery options to use. Do not commit, push, create a PR, or merge without explicit confirmation.
