# Project and Program Management Permission Design

## Goal

Use one ownership-based authorization model for projects and programs while
allowing all authenticated users to create either object.

## Roles

- An authenticated user may create a project or program.
- A project or program owner may edit it and perform its lifecycle actions.
- A program owner inherits edit and lifecycle authority over every descendant
  program and project in that program tree.
- A system administrator has all owner capabilities globally.

## Delete Rules

Owners may delete only empty leaf nodes: a program must have no child programs
or projects, and a project must have no child projects. System administrators
may retain the existing force-delete behavior for non-empty trees.

## Scope

The authorization model applies consistently to both object types. It does not
alter permissions for project membership management, workflow configuration, or
work-item operations.

## Error Handling and Verification

Rejected authenticated operations return `403`; absent credentials return
`401`. API tests must cover direct-owner access, inherited program-owner access,
unrelated-user rejection, administrator override, and leaf-only owner deletion.
