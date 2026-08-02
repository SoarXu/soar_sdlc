# Program View Project Delete Design

## Goal

Give project rows in the project-set tree the same permission-gated delete
operation and centered confirmation flow as project rows on the project page.

## Design

The project-set view will load project memberships after loading its tree. It
will evaluate project management using the same direct project, ancestor project,
and ancestor project-set ownership rules as the project page. Only users who
pass that check see the project deletion action.

The action calls a local `confirmRemoveProject` wrapper with the existing
project-page warning text, then delegates to `removeProject`. Deletion reuses
the existing project API and preserves the existing error presentation behavior.

## Testing

Add a source-contract test covering membership loading, permission-gated delete
button, exact confirmation text, and delegation to the project delete API.
