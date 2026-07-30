# Program Owner Permission Design

## Decision

`Program.owner_id` represents the accountable owner of a program and grants
governance authority over that program and every descendant program and
project. It is not a workflow role and does not make the user the owner or
current handler of requirements, tasks, test cases, test runs, or bugs.

Workflow runtime behavior is explicitly out of scope. A work-item owner is
set only by the existing workflow advanced configuration and transition logic.

## Creation

- Any authenticated user may create a root program.
- The program owner defaults to the authenticated creator when `owner_id` is
  omitted. The creator may select another active user before saving.
- Creating a child program requires governance authority on its parent. The
  child owner still defaults to the authenticated creator and may be changed.
- A creator has no lasting special authority once ownership is transferred.

## Governance Inheritance

For a program, an actor has governance authority when the actor is a system
administrator or is the owner of that program or one of its active ancestors.
For a project, the same rule is evaluated from the project's assigned program
and follows that program's ancestor chain.

Program governance includes viewing the program tree and all descendant
projects, editing program metadata and ownership, creating child programs and
projects, maintaining descendant project membership, and running project and
program lifecycle actions. It does not bypass work-item workflow permissions
or assign work-item owners.

## Ownership Transfer

The current program owner, an owner of an active ancestor program, and a
system administrator may change `owner_id`. The new owner must be an active,
non-deleted user. The transfer takes effect immediately because permissions
are derived from the current tree rather than copied into project-member rows.

## Deletion And Closure

- A program owner may delete only an empty program: no active child programs
  and no active projects are attached to it.
- A non-empty program must be closed instead. The existing closure rule that
  requires all descendants and projects to be closed remains in force.
- A system administrator may remove a non-empty program tree only after all
  descendant programs and projects are closed. Deletion remains soft deletion
  so audit history is retained.

## Permission Precedence

1. System administrator has global authority.
2. Program owner has inherited governance authority over the owned subtree.
3. Project owner has governance authority only for that project.
4. Project members retain their existing execution permissions.

There is no separate global "program manager" role. Root-program creation is
available to every authenticated user.

## Acceptance Criteria

- An authenticated user can create a root program and becomes its owner by
  default.
- Parent or ancestor program owners can manage descendant programs and
  projects without being inserted into each project's member list.
- Ownership transfer immediately revokes the former owner's inherited access
  unless another applicable authority remains.
- Program ownership alone never changes a work item's `owner_id` or bypasses
  workflow transition authorization.
- A non-administrator cannot delete a non-empty program; a closed tree can be
  removed only by an administrator.
