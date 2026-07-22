# Remove Workbench Unplanned Section Design

## Decision

Remove the `unplanned` section from the workbench contract and user interface. Normal requirements, tasks, and Bugs without an iteration do not appear anywhere on the workbench. Users schedule those items from project detail pages.

## Workbench Scope

The normal workbench sections are:

1. Pending handling
2. Unassigned
3. Exception center
4. Created, watched, and mentioned tracking

Pending, unassigned, created, watched, and mentioned items must belong to an active iteration. Planning-iteration, terminal-iteration, and uniterated normal items are excluded by the backend.

The workbench provides no historical switch, iteration-state switch, or unplanned queue.

## Exception Boundary

An uniterated item is not an exception by itself and must not enter the exception center.

The exception center may contain authorized integrity or routing violations, including:

- a non-terminal item in a terminal iteration;
- a processing state with no eligible current handler;
- inconsistent or duplicated open iteration-membership history;
- an assigned handler who is inactive, removed from the project, or unable to view the project;
- a reopen count or iteration transfer without the required audit trail.

Normal project backlog and scheduling work remain on project detail pages.

## API And Frontend Changes

- Remove `unplanned` from `WorkbenchResponse`.
- Remove the unplanned query and scheduling-role checks that exist only for that section.
- Remove the unplanned navigation entry and summary card.
- Remove unplanned workflow-action loading from the dashboard.
- Update empty-state copy and tests to describe active-iteration scope only.
- Keep active-iteration and project-permission filtering on every remaining normal section.

## Compatibility

This is an intentional API contract removal. The frontend and backend must be released together. No empty compatibility field or hidden response section is retained.

## Verification

- Backend tests prove uniterated items are absent from every normal workbench section.
- Backend tests prove an uniterated item alone does not enter the exception center.
- Frontend tests prove no `unplanned` entry, summary card, filter, or history switch exists.
- Existing active-iteration, permission, terminal-iteration integrity, and Bug reactivation tests remain green.
