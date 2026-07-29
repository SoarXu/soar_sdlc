# Workbench Terminal Tabs Design

## Goal

Allow users to review work items in active iterations that have reached a terminal workflow state, while distinguishing normal delivery completion from work that was stopped.

## Scope

The workbench adds two first-level tabs:

- `已完成`: requirements, tasks, and bugs in an active iteration whose current state is terminal and classified as `completed`.
- `已终止`: requirements, tasks, and bugs in an active iteration whose current state is terminal and classified as `terminated`.

The existing `待处理`, `未分派`, `异常中心`, and `我发起/关注` entries remain unchanged. The workbench remains an active-iteration view and does not add an iteration-history entry.

## Workflow State Classification

Workflow states gain a stable `terminal_kind` field. It is optional for non-terminal states and, for terminal states, is one of:

- `completed`: normal delivery completion, such as acceptance passed or closed.
- `terminated`: no longer progressing, such as canceled, rejected, or voided.

The workbench must rely on this configured field rather than state display names, action labels, or a last-operation heuristic. Existing terminal states with no configured value do not appear in either new tab until their workflow configuration is completed.

## Data Flow

`GET /api/v1/dashboard/workbench` continues to own authorization and active-iteration filtering. It returns two new sections after filtering work items by `state_category == terminal` and `terminal_kind`.

The frontend workbench view model exposes the sections as entry tabs and summary cards. `DashboardView.vue` renders their tables with the established filters and detail navigation. Terminal rows continue to use the existing workflow-action guard, so no ordinary state transition action is offered from these tabs.

## Validation

Backend tests cover the workflow-state configuration contract and both workbench sections, including active-iteration and project-permission scope. Frontend tests cover tab construction, counts, and rendering integration. Existing workbench tests continue to verify that pending and unassigned queues contain only non-terminal work.
