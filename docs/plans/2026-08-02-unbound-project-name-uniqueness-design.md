# Unbound Project Name Uniqueness Design

## Goal

Apply the existing same-level project-name uniqueness rule to projects without a
project set.

## Design

`_require_unique_project_name` will no longer return early when `program_id` is
null. Its existing query will instead compare active projects whose `program_id`
is null and whose `parent_id` matches the submitted project. Name normalization,
case-insensitive comparison, and self-exclusion during edits remain unchanged.

This rejects duplicate root projects without a project set and duplicate children
under the same unbound parent. Projects under different parent projects remain
valid even when their names match.

## Testing

Extend the existing project-name uniqueness acceptance tests to reject a second
unbound root project with the same name, while retaining the different-parent
allowance.
