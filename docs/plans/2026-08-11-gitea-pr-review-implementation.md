# Gitea Pull Request Review Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate Gitea pull requests into SDLC so reviewers can inspect diffs, write inline comments, and approve or request changes from the DevOps module.

**Architecture:** A Gitea adapter owns provider HTTP calls. Webhooks create an idempotent local projection of Gitea pull requests, while reviewer actions persist local audit/outbound-operation records before calling the adapter and refreshing state. The Vue DevOps module consumes SDLC-only APIs and never holds a Gitea token.

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, Pydantic, pytest, Vue 3, Axios, Element Plus, Gitea REST API and webhooks.

---

### Task 1: Add Pull Request Persistence Models and Migration

**Files:**
- Modify: `backend/app/models/devops.py`
- Create: `backend/alembic/versions/20260811_001_gitea_pull_request_review.py`
- Test: `backend/tests/test_gitea_pull_request_migration.py`

**Step 1: Write the failing migration test**

Assert that upgrading an empty test database creates pull request, pull request link, review, comment, webhook delivery, and outbound-operation tables, plus unique constraints for repository/PR number and webhook delivery identity.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_gitea_pull_request_migration.py -v`

Expected: FAIL because the migration and ORM entities do not exist.

**Step 3: Implement the minimal schema**

Add SQLAlchemy models with soft-delete fields where consistent with existing DevOps models. Extend `DevopsRepository` with `git_platform_connection_id`, `external_owner`, `external_name`, and encrypted webhook-secret storage. Add indexes for active repositories, active pull requests, external remote IDs, and pending outbound operations.

**Step 4: Run migration tests**

Run: `pytest tests/test_gitea_pull_request_migration.py -v`

Expected: PASS.

**Step 5: Commit**

Do not commit until the user selects a delivery option. Intended commit message: `feat: add Gitea pull request review schema`.

### Task 2: Build a Tested Gitea REST Adapter

**Files:**
- Create: `backend/app/services/gitea_client.py`
- Test: `backend/tests/test_gitea_client.py`

**Step 1: Write failing adapter tests**

Mock Gitea HTTP responses and assert the client sends `Authorization: token <token>`, URL-encodes owner/repository names, and supports fetching a PR, files, comments/reviews, posting an inline comment, and submitting `APPROVED` or `REQUEST_CHANGES`.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_gitea_client.py -v`

Expected: FAIL because no adapter exists.

**Step 3: Implement the adapter**

Create typed result objects and a narrow HTTP wrapper using the existing encrypted token support. Map HTTP/network/invalid-response failures to a provider-specific exception that includes a non-secret message and retryability.

**Step 4: Run adapter tests**

Run: `pytest tests/test_gitea_client.py -v`

Expected: PASS.

**Step 5: Commit**

Do not commit until the user selects a delivery option. Intended commit message: `feat: add Gitea pull request API client`.

### Task 3: Synchronize Pull Requests and Process Webhooks

**Files:**
- Modify: `backend/app/services/devops_service.py`
- Create: `backend/app/services/gitea_pull_request_service.py`
- Modify: `backend/app/controllers/devops_controller.py`
- Modify: `backend/app/views/devops_view.py`
- Test: `backend/tests/test_gitea_pull_request_sync.py`
- Test: `backend/tests/test_gitea_webhook_api.py`

**Step 1: Write failing synchronization tests**

Create a verified Gitea connection and repository, mock a Gitea PR payload, then assert the service upserts a single local PR, maps branches/SHAs/state/author, resolves `REQ-`, `TASK-`, and `BUG-` references, and assigns a non-author reviewer by the existing project/team fallback rules.

Add webhook tests that reject an invalid secret, accept a valid secret, and process a duplicate delivery only once.

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_gitea_pull_request_sync.py tests/test_gitea_webhook_api.py -v`

Expected: FAIL because the sync service and endpoint do not exist.

**Step 3: Implement synchronization and endpoint**

Implement `POST /api/v1/devops/gitea/webhook/{repository_id}` with a secret check and supported-event routing. Record webhook delivery before synchronization, use `(repository_id, external_number)` for upserts, retain the previous projection on refresh failure, and expose a protected pull-request sync endpoint for manual recovery.

**Step 4: Run synchronization tests**

Run: `pytest tests/test_gitea_pull_request_sync.py tests/test_gitea_webhook_api.py -v`

Expected: PASS.

**Step 5: Commit**

Do not commit until the user selects a delivery option. Intended commit message: `feat: sync Gitea pull requests through webhooks`.

### Task 4: Add Review, Inline Comment, and Retry APIs

**Files:**
- Modify: `backend/app/services/gitea_pull_request_service.py`
- Modify: `backend/app/controllers/devops_controller.py`
- Modify: `backend/app/views/devops_view.py`
- Test: `backend/tests/test_gitea_pull_request_review_api.py`

**Step 1: Write failing review tests**

Assert an assigned reviewer can create an inline comment with file path, side, line, and current commit SHA; can submit an approval or change request; and that a remote API failure records a failed operation without marking the local review as successful. Assert the author cannot review their own PR and unrelated users receive `403`.

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_gitea_pull_request_review_api.py -v`

Expected: FAIL because review endpoints and operation records do not exist.

**Step 3: Implement minimal review workflow**

Add read endpoints for list/detail/diff and write endpoints for comment, review decision, and retry. Persist local intent and outbound operation in one transaction, call Gitea, mark success only after a response, and then synchronize the PR. Re-authorize every retry.

**Step 4: Run review tests**

Run: `pytest tests/test_gitea_pull_request_review_api.py -v`

Expected: PASS.

**Step 5: Commit**

Do not commit until the user selects a delivery option. Intended commit message: `feat: add SDLC Gitea review actions`.

### Task 5: Replace the DevOps Review Experience with Pull Requests

**Files:**
- Modify: `frontend/src/api/devops.js`
- Modify: `frontend/src/views/DevopsView.vue`
- Create: `frontend/src/components/PullRequestDiffViewer.vue`
- Test: `frontend/src/views/devopsGiteaPullRequests.test.mjs`
- Test: `frontend/src/components/pullRequestDiffViewer.test.mjs`

**Step 1: Write failing component/view tests**

Assert the PR list requests SDLC pull-request APIs, displays source/target branches and review state, opens a detail view, presents a line-comment action for changed lines, submits an approval/change-request action, and surfaces failed operations with retry affordances.

**Step 2: Run test to verify it fails**

Run: `npm test -- --run src/views/devopsGiteaPullRequests.test.mjs src/components/pullRequestDiffViewer.test.mjs`

Expected: FAIL because the API functions and UI components do not exist.

**Step 3: Implement the frontend**

Use Element Plus tables, tabs, dialogs, and tooltips consistent with `DevopsView.vue`. Keep Gitea tokens and raw webhook secrets out of all frontend responses. Preserve existing Commit/Jenkins tabs as history and add `Pull Requests` and `My Reviews` as the primary review tabs.

**Step 4: Run frontend tests**

Run: `npm test -- --run src/views/devopsGiteaPullRequests.test.mjs src/components/pullRequestDiffViewer.test.mjs`

Expected: PASS.

**Step 5: Commit**

Do not commit until the user selects a delivery option. Intended commit message: `feat: add Gitea pull request review UI`.

### Task 6: Perform End-to-End Local Verification

**Files:**
- Modify: `README.md`
- Test: `backend/tests/test_gitea_pull_request_sync.py`
- Test: `backend/tests/test_gitea_pull_request_review_api.py`

**Step 1: Document local configuration**

Add the required `GIT_PLATFORM_ENCRYPTION_KEY`, the local Gitea base URL `http://localhost:3002`, personal-access-token scopes, and the webhook endpoint. State the host-address rule for containerized or separate-host deployments.

**Step 2: Run focused backend suite**

Run: `pytest tests/test_git_platform_connections_api.py tests/test_gitea_client.py tests/test_gitea_pull_request_migration.py tests/test_gitea_pull_request_sync.py tests/test_gitea_webhook_api.py tests/test_gitea_pull_request_review_api.py -v`

Expected: PASS.

**Step 3: Run focused frontend suite**

Run: `npm test -- --run src/views/devopsGitPlatforms.test.mjs src/views/devopsGiteaPullRequests.test.mjs src/components/pullRequestDiffViewer.test.mjs`

Expected: PASS.

**Step 4: Manually verify the local flow**

Create a Gitea repository and pull request, configure the SDLC Gitea connection/repository/webhook, trigger synchronization, add an inline SDLC comment, submit a decision, and confirm both appear in the Gitea PR.

**Step 5: Commit**

Do not commit until the user selects a delivery option. Intended commit message: `docs: document local Gitea pull request review setup`.
