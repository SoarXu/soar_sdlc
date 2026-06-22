# Iteration Scope Detail Design

## Goal

Build iteration detail management around existing work items. Iterations can include requirements and standalone tasks from multiple linked projects at any project-tree level, without creating tasks inside the iteration page.

## Confirmed Rules

- An iteration can link to multiple projects at any project-tree level.
- The selectable scope for requirements and tasks includes the linked projects and all descendant projects. If a child project is linked directly, the iteration remains attached to that child project after project tree moves.
- Requirements are linked through `requirements.iteration_id`.
- A requirement can belong to only one iteration.
- Tasks can be directly linked to an iteration through `tasks.iteration_id`.
- A task may be shown in an iteration because it belongs to a linked requirement, or because it is directly linked to the iteration.
- The iteration detail page does not create tasks. It only links and unlinks existing tasks.
- Removing a requirement from an iteration clears `requirements.iteration_id`; tasks under that requirement disappear from the iteration task list automatically.
- Removing a directly linked task clears `tasks.iteration_id`; the task itself is not deleted.
- Test cases are not directly linked to iterations. The iteration test case list is derived from linked requirements.
- Overview test coverage is `requirements with at least one test case / all linked requirements`.
- Overview progress is `closed linked requirements / all linked requirements`.

## User Experience

The global iteration list remains the entry point for cross-project iteration management. Iteration names link to a new detail page with tabs:

- Overview
- Requirements
- Tasks
- Test Cases

The Requirements tab shows requirements grouped by project tree. It provides a link action that opens selectable requirements in scope, excluding requirements already linked to any iteration. Each linked requirement can be removed.

The Tasks tab shows two groups:

- Tasks brought in by linked requirements.
- Tasks directly linked to the iteration.

The direct task link action opens selectable tasks in scope, excluding tasks already directly linked to any iteration. Removing a task only affects direct task links.

## Data Model

Reuse `requirements.iteration_id`.

Add `tasks.iteration_id BIGINT UNSIGNED NULL` for direct task links.

Keep `iteration_projects` as the iteration scope table.

## API Shape

- `GET /api/v1/iterations/{id}/detail`
  Returns the iteration, linked projects, scoped project tree, linked requirements, iteration tasks, test cases, and overview metrics.
- `GET /api/v1/iterations/{id}/available-requirements`
  Returns requirements in scope with `iteration_id IS NULL`.
- `POST /api/v1/iterations/{id}/requirements`
  Body: `{ "requirement_ids": [1, 2] }`.
- `DELETE /api/v1/iterations/{id}/requirements/{requirement_id}`
  Clears the requirement iteration.
- `GET /api/v1/iterations/{id}/available-tasks`
  Returns tasks in scope with no direct iteration link.
- `POST /api/v1/iterations/{id}/tasks`
  Body: `{ "task_ids": [1, 2] }`.
- `DELETE /api/v1/iterations/{id}/tasks/{task_id}`
  Clears the task direct iteration link.

## Error Handling

- Linking a requirement outside iteration project scope returns `400`.
- Linking a requirement already linked to another iteration returns `400`.
- Linking a task outside iteration project scope returns `400`.
- Linking a task already directly linked to another iteration returns `400`.
- Removing an object not linked to the iteration is idempotent where practical.

## Testing

Backend tests cover:

- Linked project scope includes descendant projects.
- Linked requirements appear in iteration detail.
- Requirements already in one iteration are excluded from another iteration's available list.
- Directly linked tasks appear alongside tasks brought in by requirements.
- Removing a requirement removes its brought-in tasks from detail.
- Coverage and progress metrics use linked requirements only.

Frontend verification covers:

- Iteration names navigate to detail.
- Link and remove buttons call backend APIs.
- Requirements are grouped by project tree.
- Overview metrics render correctly.
