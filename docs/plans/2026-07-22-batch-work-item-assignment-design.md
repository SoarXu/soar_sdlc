# Batch Work Item Assignment Design

## Scope

Add row selection and batch assignment to the requirement, task, and bug list pages. Test cases are explicitly excluded: `default_tester_id` is a default tester for a case, while the actual tester is assigned when the case is added to a test run.

## Interaction

- Add a selection column to the requirement, task, and bug tables.
- A row can be selected only when the current user has a supported, available assignment transition and its project is not terminal.
- Selection is limited to one project and one object type. After the first selection, rows from other projects are disabled with an explanation.
- Selection exists only for the current page. Changing page, filters, project scope, or reloading data clears it.
- When one or more rows are selected, show a batch action area beside the table pagination: selected count and an "Assign to" action.
- The assignee picker is searchable and contains only the intersection of users permitted by every selected transition.
- Before submission, show the object type, selected count, destination handler, and a reason field when any selected transition requires a delegation reason.

## API and Runtime

Extend the runtime transition read model with batch-assignment metadata. For an action that supports an explicit next handler without custom form input, expose whether it can be batch assigned, whether it requires a reason, and the eligible target member IDs.

Add `POST /workflow-runtime/assignments/batch`.

The request contains one object type, one project ID, one destination handler, an optional delegation reason, and items consisting of `id` and `transition_id`.

The service must:

1. Re-read and validate every item: object type, project, active state, available transition, actor permission, target-member role, and any required reason.
2. Reject mixed projects, mixed object types, duplicated items, empty input, and non-batchable transitions.
3. Run every transition through the existing workflow runtime logic in a single database transaction.
4. Preserve existing handler routing, status-operation logs, audit history, and workflow notifications for each item.
5. Commit only when every item succeeds. On any error, roll back all item changes and logs.

The existing single-item transition endpoint remains unchanged. The shared runtime implementation is refactored only as necessary to allow it and the batch endpoint to share validation and execution without committing each item independently.

## Frontend Structure

Create a shared batch-assignment control for the three list pages. Each page retains table selection state and its already-loaded workflow transition data; the shared control calculates candidate intersections, prompts for confirmation, invokes the batch API, and presents results.

The feature must not infer behavior from labels such as "Assign" or "Transfer". It uses the runtime metadata and the returned transition ID.

## Failure Handling

- Disable the batch controls and row selection while a request is pending.
- If no shared eligible assignee exists, disable submission and explain why.
- On validation failure caused by a concurrent change, show the affected item identifiers and reasons, keep the selection, and make no changes.
- On success, refresh the list, clear selection, and report the destination handler and completed count.

## Verification

- Unit tests for batch metadata, target-member intersections, payload construction, selection reset, same-project enforcement, and confirmation validation.
- API tests for requirements, tasks, and bugs covering successful assignment, permission and role checks, required reasons, invalid states, duplicate and mixed-project requests, audit/log creation, and transaction rollback.
- Component tests for table selection, disabled rows, pagination reset, candidate filtering, loading state, and error rendering.
- Production frontend build and focused backend test suite.
- Browser checks at desktop and narrow widths to confirm the bottom action area, pagination, and actions do not overlap.
