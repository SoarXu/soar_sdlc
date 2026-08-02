# Project Name Duplicate Feedback Design

## Goal

Display the same Chinese non-modal error message used for duplicate program
names when a project name duplicates another project in the same hierarchy,
while preserving the current form for correction.

## Existing Rule

The backend already enforces case-insensitive project-name uniqueness within the
same `program_id` and `parent_id`. The update path excludes the current project.
Therefore, projects in different programs or below different parent projects may
use the same name. This rule will remain unchanged.

## Design

Both project-create/edit entry points (`ProgramsView` and `ProjectsView`) will
catch rejected save requests. A rejected request keeps its dialog and reactive
form state open, then uses `ElMessage.error` with the same error-message helper
as the project-set save flow. A successful save continues to close the dialog
and refresh the data.

## Testing

Add source-contract tests for both views to require an error catch that calls
`ElMessage.error(actionErrorMessage(...))`. Keep the existing backend regression
test covering duplicate rejection in the same program and parent scope, plus
successful reuse in a different program.
