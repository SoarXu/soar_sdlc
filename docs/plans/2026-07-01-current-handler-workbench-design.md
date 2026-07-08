# Current Handler Workbench Design

## Goal

Adjust requirements, tasks, test cases, and bugs so their visible owner means "current handler" rather than a fixed long-term owner. The workbench should show the items the current user needs to process now.

## Problem

Current fields such as `requirements.owner_id`, `tasks.owner_id`, `test_cases.default_tester_id`, and `bugs.owner_id` are used as fixed default assignees. The workbench then filters mostly by project participation and role, so users see many items that are in their project but are not their current responsibility.

Leadership expects a workflow-driven queue:

- Status transitions move the item to the next handler.
- Users can manually assign an item to another person.
- The workbench defaults to "my current pending work".
- Team leads can still inspect team work.

## Recommended Model

Keep existing `owner_id` columns for now, but formalize them as current handler fields:

- `requirements.owner_id`: current requirement handler.
- `tasks.owner_id`: current task handler.
- `bugs.owner_id`: current bug handler.
- `test_cases.default_tester_id`: keep as default tester for now; when execution workflow becomes richer, add a separate current handler field.

This avoids a broad database migration while fixing the semantics that drive the workbench.

Use stable source fields for non-current ownership:

- `requirements.proposer_id`: proposer.
- `bugs.reporter_id`: reporter.
- `creator_id` / `updater_id`: audit ownership.
- `projects.owner_id`, `iterations.owner_id`: management responsibility.

## Assignment Rules

Every status action may calculate a `next_owner_id`.

Default transitions:

| Object | Action | Target Status | Next Handler |
| --- | --- | --- | --- |
| Requirement | create/draft | draft | product/requirement owner |
| Requirement | activate | active | developer or configured requirement handler |
| Requirement | complete / submit validation | pending_validation | tester/test lead |
| Requirement | validation failed | validation_failed | developer |
| Requirement | done/closed | terminal | keep last handler, hide from my pending work |
| Task | create/activate | todo/doing | developer |
| Task | complete | done | keep last handler, hide from my pending work |
| Bug | create | open | developer confirmation handler |
| Bug | confirm/start fixing | fixing | developer/fixer |
| Bug | resolve | verifying | tester/verifier |
| Bug | verify failed / activate | reopened | developer/fixer |
| Bug | close | closed | keep last handler, hide from my pending work |

Manual assignment should override the calculated handler until the next workflow action recalculates it.

## API Changes

Add explicit assign endpoints:

- `POST /api/v1/requirements/{id}/assign`
- `POST /api/v1/tasks/{id}/assign`
- `POST /api/v1/bugs/{id}/assign`

Payload:

```json
{
  "owner_id": 12,
  "remark": "转给张三处理"
}
```

The endpoint updates `owner_id` and writes a status operation log with action `assign`. If the object is terminal (`done`, `closed`), assignment should be rejected unless a later design explicitly supports historical reassignment.

## History

`status_operation_log` should record assignment changes. The current table does not store from/to owner directly, so use structured text in `remark` initially:

```text
assign owner: 5 -> 12. 转给张三处理
```

If this becomes central to reporting, add `from_owner_id` and `to_owner_id` columns later.

## Workbench Rules

Default "my workbench":

- Show only non-terminal items where `owner_id = current_user_id`.
- For test cases, keep using `default_tester_id = current_user_id` until a separate execution-handler model exists.
- Hide terminal statuses by default:
  - Requirement: `done`, `closed`
  - Task: `done`, `closed`
  - Bug: `closed`
  - Test case: no terminal hiding until execution plan is separated.

Lead/team view:

- Project owner, product manager, development lead, and test lead can switch to a team view.
- Team view uses project participation/scope rules and can filter by handler.

Admin view:

- Admin can see all items and filter by handler.

## Frontend Changes

Rename visible labels from "负责人" to "当前处理人" where the table/list is about active work:

- Workbench list and cards.
- Requirement/task/bug list columns.
- Detail pages near status actions.

Add an "指派" action for non-terminal requirement/task/bug rows. The dialog contains:

- Handler select.
- Remark textarea.

After assignment, refresh the row/workbench and show the new current handler.

## Testing

Backend tests should prove:

- Requirement submit validation moves handler to tester.
- Bug resolve moves handler to verifier.
- Bug activation after close/reopen moves handler to developer.
- Manual assign updates `owner_id` and writes history.
- My workbench only returns non-terminal items assigned to the current user.
- Team view still returns scoped project items.

Frontend tests/build should prove:

- Workbench renders "当前处理人".
- Assign dialog calls the correct endpoint.
- Terminal items are not shown in my pending work by default.

## Open Decisions

1. Whether `test_cases.default_tester_id` should be renamed or a new `owner_id` added for current test execution handler.
2. Whether assignment history needs first-class `from_owner_id` and `to_owner_id` columns immediately.
3. Whether manual assignment should persist across every status transition or only until the next transition.
