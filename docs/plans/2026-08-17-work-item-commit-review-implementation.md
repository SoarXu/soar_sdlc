# 工作项提交追溯与代码评审 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 让需求、任务、缺陷详情页可靠追溯关联提交，支持 Git 平台外链和本地 Diff 评审，并只在显式提请评审时自动进入待评审状态。

**Architecture:** 保持 `DevopsCommit` 为提交事实、`DevopsCommitLink` 为多对多关联。扩展提交的 Diff 获取状态，并以 `WorkItemReviewRound` 加新的 Commit 快照表冻结一次评审的范围。提交入库统一解析引用和评审标记；普通提交只建链，显式标记才经现有工作流服务进入待评审。详情页与 DevOps 工作台均使用同一评审轮次 API 和 Diff 抽屉。

**Tech Stack:** FastAPI、SQLAlchemy、Alembic、Pydantic、pytest、Vue 3、Element Plus、Axios、Gitea/GitLab/GitHub REST API。

---

### Task 1: Persist Diff Retrieval State and Review-Commit Snapshots

**Files:**
- Modify: `backend/app/models/devops.py`
- Create: `backend/alembic/versions/20260817_001_work_item_commit_review.py`
- Modify: `backend/tests/conftest.py`
- Create: `backend/tests/test_work_item_commit_review_migration.py`

**Step 1: Write the failing migration tests**

Assert that metadata declares `DevopsCommit.diff_status`, `diff_fetched_at`, `diff_error`, and a `WorkItemReviewCommit` model with a unique `(review_round_id, commit_id)` constraint. Upgrade an isolated database and assert the new columns/table/indexes exist.

```python
def test_review_commit_snapshot_has_unique_round_commit_pair():
    constraint_names = {item.name for item in WorkItemReviewCommit.__table__.constraints}
    assert "uk_work_item_review_commit" in constraint_names
```

**Step 2: Run the migration test to verify it fails**

Run: `python -m pytest tests/test_work_item_commit_review_migration.py -q`

Expected: FAIL because the model and migration do not yet exist.

**Step 3: Implement the smallest schema extension**

- Add nullable `diff_fetched_at`, `diff_error` and non-null `diff_status` with default `pending` to `DevopsCommit`.
- Add `WorkItemReviewCommit` with `review_round_id`, `commit_id`, `sort_order`, `create_time`, unique constraint and round index.
- Make the Alembic migration idempotent with inspector checks, following existing migrations.
- Add the new table to `TRACKED_TABLES` in `conftest.py` so fixture cleanup does not leak rows.

**Step 4: Re-run the migration test**

Run: `python -m pytest tests/test_work_item_commit_review_migration.py -q`

Expected: PASS.

**Step 5: Commit**

Do not commit until the user selects a delivery option. Intended message: `feat: persist commit diff and review snapshots`.

### Task 2: Separate Reference Binding from Review-Ready Triggering

**Files:**
- Modify: `backend/app/services/devops_service.py`
- Modify: `backend/app/services/work_item_review_service.py`
- Modify: `backend/tests/test_git_triggered_work_item_review.py`
- Modify: `backend/tests/test_devops_code_review_api.py`

**Step 1: Write failing behavioral tests**

Cover the exact policy boundary:

```python
def test_plain_linked_commit_keeps_work_item_in_development(client):
    commit = ingest(client, f"TASK-{task_id} partial implementation")
    assert linked_commit_ids(client, "task", task_id) == [commit["id"]]
    assert current_status(client, "task", task_id) == "处理中"

def test_review_ready_commit_creates_round_and_enters_pending_review(client):
    ingest(client, f"TASK-{task_id} implementation complete #review")
    assert current_status(client, "task", task_id) == "待评审"
```

Add cases for `Review-Ready: true`, multiple `REQ/TASK/BUG` references, duplicate webhook/ingest idempotency, and a marker for a work item that is not in a state with `submit_review`.

**Step 2: Run focused tests to verify failure**

Run: `python -m pytest tests/test_git_triggered_work_item_review.py tests/test_devops_code_review_api.py -q`

Expected: FAIL because current ingestion invokes `trigger_linked_work_item_reviews` for every linked Commit.

**Step 3: Implement explicit review-ready parsing**

- Keep `resolve_commit_references()` responsible only for `REQ`/`TASK`/`BUG` association.
- Add a pure `is_review_ready(message: str) -> bool` that matches standalone `#review` and a case-insensitive `Review-Ready: true` trailer.
- Call review-round creation only when the parser returns true.
- Keep links regardless of marker validity; never silently drop a normal Commit.

**Step 4: Re-run focused tests**

Run: `python -m pytest tests/test_git_triggered_work_item_review.py tests/test_devops_code_review_api.py -q`

Expected: PASS.

**Step 5: Commit**

Do not commit until the user selects a delivery option. Intended message: `fix: require explicit review-ready commit marker`.

### Task 3: Freeze Review Scope and Invalidate It on New Commits

**Files:**
- Modify: `backend/app/services/work_item_review_service.py`
- Modify: `backend/app/models/devops.py`
- Modify: `backend/tests/test_git_triggered_work_item_review.py`
- Modify: `backend/tests/test_work_item_review_api.py`

**Step 1: Write failing review-round tests**

Assert that a review-ready Commit snapshots every linked Commit for the same work item up to that point, in commit order. Assert a new later linked Commit while the round is open:

- marks the old round `superseded`;
- clears its active key;
- moves the item from `待评审` back to `处理中` using the configured return transition;
- requires a later review-ready Commit to open the next round.

Also assert `decide_review_round()` rejects superseded rounds.

**Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_git_triggered_work_item_review.py tests/test_work_item_review_api.py -q`

Expected: FAIL because the existing round only stores `latest_commit_id` and mutates it in place.

**Step 3: Implement immutable round snapshots**

- Add `superseded` as a supported review-round status and make `active_key` nullable for it.
- Create `WorkItemReviewCommit` records when opening a round; include all linked Commit IDs ordered by commit time then ID.
- On later linked Commit, supersede the open round rather than changing its `latest_commit_id`.
- Find a configured `reject_review`/return-to-development transition for the item and execute it through `workflow_runtime_service`; if no return transition is available, retain state and return a controlled conflict to the ingestion caller for auditability.
- Only allow decision on `open` rounds and only when no later linked Commit exists.

**Step 4: Re-run tests**

Run: `python -m pytest tests/test_git_triggered_work_item_review.py tests/test_work_item_review_api.py -q`

Expected: PASS.

**Step 5: Commit**

Do not commit until the user selects a delivery option. Intended message: `feat: freeze work item review commit scope`.

### Task 4: Add Provider-Neutral Commit Diff Retrieval and Caching

**Files:**
- Create: `backend/app/services/git_commit_diff_service.py`
- Modify: `backend/app/services/git_platform_service.py`
- Modify: `backend/app/services/devops_service.py`
- Modify: `backend/app/models/devops.py`
- Create: `backend/tests/test_git_commit_diff_service.py`
- Modify: `backend/tests/test_git_platform_connections_api.py`

**Step 1: Write failing adapter/service tests**

Mock provider HTTP calls and assert provider-specific requests are built correctly:

- Gitea: repository commit endpoint plus diff endpoint.
- GitLab: project commit diff endpoint.
- GitHub: repository commit endpoint returning file patches.

Test that successful fetch sets `diff_status="available"`, stores normalized unified text or structured JSON, stamps `diff_fetched_at`, and clears `diff_error`. Test empty Diff (`empty`) and timeout/401/404 (`failed`) without exposing a token.

**Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_git_commit_diff_service.py -q`

Expected: FAIL because no provider-neutral Commit Diff service exists.

**Step 3: Implement the retrieval service**

- Resolve the repository's Git platform connection using explicit repository-to-connection metadata. Add that metadata in a narrowly scoped migration only if it is absent from the current repository model.
- Reuse encrypted token handling from `git_platform_service`; never include decrypted secrets in exception text.
- Normalize external diffs to the input accepted by `CommitDiffViewer`.
- Do not fetch automatically on every list call. Fetch only when the explicit API is called or a review detail needs missing Diff.

**Step 4: Re-run the service tests**

Run: `python -m pytest tests/test_git_commit_diff_service.py tests/test_git_platform_connections_api.py -q`

Expected: PASS.

**Step 5: Commit**

Do not commit until the user selects a delivery option. Intended message: `feat: fetch and cache commit diffs from Git platforms`.

### Task 5: Expose Commit Link, Diff State, and Review Detail APIs

**Files:**
- Modify: `backend/app/views/devops_view.py`
- Modify: `backend/app/controllers/devops_controller.py`
- Modify: `backend/app/services/devops_service.py`
- Modify: `backend/app/services/work_item_review_service.py`
- Create: `backend/tests/test_work_item_commit_review_api.py`

**Step 1: Write failing API tests**

Test these API contracts:

```text
GET  /devops/commits?object_type=task&object_id=42
GET  /devops/work-item-reviews/{round_id}/commits
POST /devops/commits/{commit_id}/fetch-diff
POST /devops/work-item-reviews/{round_id}/decision
```

Assert commit list rows include `web_url`, Diff state and review summary. Assert review detail returns only the frozen snapshot, not all historical links. Assert no-Commit rounds cannot be approved and unauthorized users receive `403`.

**Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_work_item_commit_review_api.py -q`

Expected: FAIL because the review detail and fetch-Diff endpoints do not exist.

**Step 3: Implement response models and endpoints**

- Add typed Pydantic read models for Diff state, commit review summary and round Commit detail.
- Add a protected fetch-Diff command for system administrators and assigned review users; derive authorization from the linked work item rather than trusting client-supplied object IDs.
- Add `GET /work-item-reviews/{id}/commits`; include aggregate Diff in deterministic Commit order.
- Preserve existing `/devops/commits` compatibility while extending its response shape.

**Step 4: Re-run tests**

Run: `python -m pytest tests/test_work_item_commit_review_api.py tests/test_work_item_review_api.py -q`

Expected: PASS.

**Step 5: Commit**

Do not commit until the user selects a delivery option. Intended message: `feat: expose work item commit review APIs`.

### Task 6: Build the Shared Detail-Page Commit and Review Experience

**Files:**
- Modify: `frontend/src/api/devops.js`
- Modify: `frontend/src/components/CommitRecordsPanel.vue`
- Modify: `frontend/src/components/CommitDiffViewer.vue`
- Create: `frontend/src/components/WorkItemCommitReviewDrawer.vue`
- Modify: `frontend/src/views/RequirementDetailView.vue`
- Modify: `frontend/src/views/TaskDetailView.vue`
- Modify: `frontend/src/views/BugDetailView.vue`
- Create: `frontend/src/components/workItemCommitReviewDrawer.test.mjs`
- Modify: `frontend/src/components/commitRecordsPanel.test.mjs` (create if absent)

**Step 1: Write failing component/source tests**

Assert the shared panel is mounted by all three detail views and that it:

- renders SHA as an in-app Diff command;
- renders a tooltip-equipped external-link icon only when `web_url` exists;
- exposes Diff state and review status;
- exposes the review command only for a pending-review item and authorized user;
- opens the drawer with a frozen round, fetches missing Diff once, and disables decision for superseded rounds;
- shows the required no-Commit explanation rather than an empty review screen.

**Step 2: Run tests to verify failure**

Run: `npm run test -- workItemCommitReviewDrawer commitRecordsPanel`

Expected: FAIL because the shared review drawer and status interactions do not exist.

**Step 3: Implement the UI**

- Keep `CommitDiffViewer` as the renderer; do not create a second Diff parser.
- Use a dedicated review drawer that presents summary, Commit selector, Diff, overall remark and approve/reject commands.
- Use Lucide/Element Plus external-link icon with a tooltip, `window.open(web_url, "_blank", "noopener")`, and no visible text-only URL control.
- Reload the panel after fetch or decision so the details page and DevOps page consume the same persisted state.
- Keep the detail layouts compact; the Commit panel is a full-width detail section, not a nested decorative card.

**Step 4: Run frontend tests and build**

Run: `npm run test -- workItemCommitReviewDrawer commitRecordsPanel`

Run: `npm run build`

Expected: all selected tests pass and Vite build exits 0.

**Step 5: Commit**

Do not commit until the user selects a delivery option. Intended message: `feat: add work item commit review drawer`.

### Task 7: Align DevOps Workbench and Perform End-to-End Verification

**Files:**
- Modify: `frontend/src/views/DevopsView.vue`
- Modify: `frontend/src/views/gitTriggeredReviewWorkbench.test.mjs`
- Modify: `backend/tests/test_dashboard_workbench_api.py`
- Modify: `README.md`

**Step 1: Write failing integration tests**

Assert DevOps workbench displays the same review-round status and latest frozen Commit as the detail page. Assert a decision made from either location is reflected after refresh in the other.

**Step 2: Run tests to verify failure**

Run: `python -m pytest tests/test_dashboard_workbench_api.py -q -k review`

Run: `npm run test -- gitTriggeredReviewWorkbench`

Expected: FAIL because the workbench does not consume review snapshot detail/status.

**Step 3: Implement consistency updates and documentation**

- Make DevOps rows navigate to the same review drawer/detail route rather than maintaining a separate decision path.
- Document commit message syntax, Git platform connection prerequisites, Diff retrieval behavior, external-link behavior, and the no-Commit review guard.

**Step 4: Verify the full focused flow**

Run:

```powershell
cd backend
python -m pytest tests/test_work_item_commit_review_migration.py tests/test_git_triggered_work_item_review.py tests/test_git_commit_diff_service.py tests/test_work_item_commit_review_api.py tests/test_work_item_review_api.py -q
cd ../frontend
npm run test -- workItemCommitReviewDrawer commitRecordsPanel gitTriggeredReviewWorkbench
npm run build
```

Manual verification:

1. Create one requirement, one task and one bug in development state.
2. Ingest a normal `REQ/TASK/BUG` Commit and confirm all three detail pages show it while state remains development.
3. Ingest a `#review` Commit, confirm only linked work items enter pending review and their review buttons open the frozen Diff.
4. Add a later normal Commit, confirm the old review is superseded and the item returns to development.
5. Submit a new review-ready Commit, fetch missing Diff from a configured Gitea connection, approve it, and verify the existing workflow advances.
6. Click external-link icons for Gitea, GitLab and GitHub fixtures and verify correct platform URLs open.

**Step 5: Commit**

Do not commit until the user selects a delivery option. Intended message: `feat: unify work item commit review workflow`.
