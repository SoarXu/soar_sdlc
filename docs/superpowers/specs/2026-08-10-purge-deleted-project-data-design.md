# Purge Deleted Project Data Design

## Goal

Keep deleted project rows as tombstones, but permanently remove every business
record owned by those projects so stale requirements, tasks, bugs, tests, and
their associations cannot participate in workflow or workbench queries.

## Root Cause

Project deletion currently marks work items and unshared iterations as deleted.
Historical projects deleted before that cascade was introduced still own live
or soft-deleted rows. A stale requirement in the project work pool violates the
requirement-pool invariant, causing the workbench batch transition request to
return `409 REQUIREMENT_POOL_INTEGRITY_ERROR`; the frontend then has no action
data to render for otherwise valid items.

## Data Boundary

- Preserve rows in `projects` with `deleted = 1` as identity tombstones.
- Clear each deleted project's `requirement_pool_iteration_id` before deleting
  the referenced iteration.
- Permanently remove records whose `project_id` belongs to the deleted project
  tree: requirements, tasks, bugs, test cases, test runs, project members,
  exception rules, owned business components, and iteration scope rows.
- Permanently remove dependent and polymorphic records for those objects:
  execution logs, test-run cases, comments, watches, status operations, audits,
  iteration history, relations on either side, tags, attachment metadata,
  custom field values, external mappings, commit links, component assignments,
  workflow migration logs, notifications, and notification delivery logs.
- Remove project-scoped notification channel configuration. Shared workflow
  definitions, workflow schemes, tags, users, DevOps commits, and file blobs are
  not owned exclusively by the deleted project and remain.
- A requirement, task, bug, or test case that only has `source_project_id`
  pointing to a deleted project remains when its owning `project_id` is active.
  This preserves imported work-item snapshots in active projects.
- A business component owned by or sourced from a deleted project is removed.
  An active work item assigned to that component remains, but its component
  binding is removed.
- Surviving tasks and test cases have `requirement_id` cleared when it points to
  a deleted requirement. Surviving bugs similarly clear references to deleted
  requirements, tasks, test cases, and test runs.

## Iteration Safety

Candidate iterations are collected before deletion from project requirement
pool pointers, project scope rows, and owned work-item iteration references.
The deleted project's scope is removed first. A candidate iteration is deleted
only when no active non-target project has scope membership, a requirement-pool
pointer, or a surviving requirement, task, bug, test case, or test run that
references it. Shared iterations remain and retain only active project scope.
Unrelated orphan iterations are outside the candidate set and remain.

## Architecture

### Historical Cleanup

Alembic revision `20260810_001` contains a self-contained SQLAlchemy Core helper
that discovers all existing `projects.deleted = 1` rows and purges their object
graphs. It materializes IDs before deleting, uses portable `SELECT`, `UPDATE`,
and `DELETE` statements, and returns per-table counts. It does not disable
foreign keys, use `DELETE RETURNING`, or use MySQL join-delete syntax. Running
the helper again returns zero deletions, making the migration idempotent.

### Future Project Deletion

`project_data_purge_service.py` implements the same boundary with the current
ORM models and a caller-owned `Session`. `delete_project` collects the active
project tree, invokes the purger, marks only the project rows as deleted, and
commits once. The purger never commits or rolls back, so any failure leaves the
project and all children unchanged in the transaction.

The migration intentionally does not import the application service. This keeps
historical migration replay independent of future model and service changes.

## Deletion Order

1. Materialize project, object, comment, notification, component, and candidate
   iteration IDs.
2. Delete notification delivery rows and notifications.
3. Clear bare references from surviving rows, then delete polymorphic
   associations, logs, histories, execution rows, and component assignments.
4. Delete owned components, members, exception rules, and project scope rows.
5. Delete bugs, test runs, test cases, tasks, and requirements.
6. Clear tombstone requirement-pool pointers.
7. Re-evaluate candidate iteration ownership and delete only safe iterations and
   completion snapshots.
8. Leave project rows for the caller or migration to preserve as tombstones.

## Verification

- An in-memory SQLite migration test enables foreign keys, seeds deleted and
  active object graphs plus exclusive/shared/unrelated iterations, and verifies
  complete removal, active-data preservation, revision linkage, and idempotency.
- Existing project API tests add database-level assertions proving child rows
  are absent rather than merely hidden by `deleted = 1` filters.
- Shared-iteration API coverage proves the active project, work item, pool, and
  membership survive unchanged.
- Focused tests, the complete backend suite, `alembic upgrade head`, residual
  count queries, and the original workbench batch-operation request form the
  completion gate.
