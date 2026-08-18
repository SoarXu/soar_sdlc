# Git-Triggered Work Item Review Design

## Goal

Require a successful Git commit containing `REQ-<id>`, `TASK-<id>`, or
`BUG-<id>` to trigger review for the linked SDLC work item. The work item moves
from development to review, creates a workbench task for a development lead,
and cannot continue until the review is approved.

## Trigger and Lifecycle

When SDLC ingests a new Commit, it resolves all referenced requirements, tasks,
and bugs. For each linked item in a development state, the service transitions
the item through its configured `submit_review` transition into `待评审`.

It creates one active review round per `(object_type, object_id)`, records the
triggering commit as the latest commit, and assigns the review task to a user
with the `development_lead` role. If the item is already `待评审`, an additional
linked commit updates the same open review round and its latest commit/Diff;
the item remains in review.

Development leads can approve or reject:

- Approval closes the review round and task, records the decision, and uses
  the configured `approve_review` transition to reach the preconfigured next
  workflow state.
- Rejection closes the review round as rejected, keeps the review comment, and
  uses `reject_review` to return the item to `开发中`.

After rejection, a later linked commit starts a new review round.

## Workflow Model

The default Requirement, Task, and Bug templates receive these nodes and
transitions:

```text
开发中 -- submit_review --> 待评审 -- approve_review --> 后续状态
                       \-- reject_review --> 开发中
```

`submit_review` is system-triggered by Git ingestion. `approve_review` and
`reject_review` allow only `development_lead`. Existing project-specific
workflows are never overwritten: an idempotent migration installs the review
subgraph only when recognizable development and successor states exist; other
definitions are reported for administrator configuration in the workflow UI.

## Data and Workbench

Add a work-item review-round entity containing object reference, latest commit,
reviewer, decision, status, timestamps, and remark. It is separate from the
legacy commit-level review task so one commit can produce review rounds for
multiple work items.

The dashboard workbench adds a `待我评审` section for active rounds assigned to
the current development lead. Each entry links to the work item and latest
commit Diff. The existing DevOps Code Review list displays the same active
round through a linked entry rather than creating duplicate independent tasks.

## Safety Rules

Only successfully ingested commits can trigger a workflow transition. Duplicate
commit deliveries and repeated references are idempotent. If a required review
transition is missing, the commit remains linked but no work item status is
changed; this is surfaced as an actionable configuration exception rather than
silently bypassing review.

## Verification

Tests cover all three object types, multi-ID commits, waiting-review updates,
approval, rejection, duplicate ingestion, unauthorized decisions, and
workbench visibility. Browser verification demonstrates `REQ-1505`: Git
commit -> 待评审 -> development lead workbench -> approve/reject.
