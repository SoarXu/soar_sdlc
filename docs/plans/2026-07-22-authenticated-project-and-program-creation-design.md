# Authenticated Project and Program Creation Design

## Goal

Allow every authenticated user to create projects and programs. Do not require
the `system_admin` role for creation.

## Scope

- `POST /api/v1/projects` accepts requests from any authenticated user.
- `POST /api/v1/programs` accepts requests from any authenticated user.
- Unauthenticated creation requests continue to return `401`.
- Project creation controls are visible to every authenticated user.

## Non-Goals

Existing permissions for editing, deleting, managing members, and performing
status transitions remain unchanged.

## Design

Replace the system-administrator dependency on the two creation endpoints with
the existing authenticated-user dependency. The resolved user is intentionally
not used by the creation services; it establishes the authentication boundary.

Remove the system-administrator condition from the project-list creation
controls. The project-program tree already renders its creation controls
without a role condition, so no visibility change is needed there.

## Verification

Add API coverage showing a non-administrator authenticated user can create a
project and a program. The same test verifies anonymous requests remain
unauthorized. Run the focused API test file and the relevant frontend tests.
