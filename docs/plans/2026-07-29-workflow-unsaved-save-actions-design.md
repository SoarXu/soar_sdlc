# Workflow Unsaved Save Actions Design

## Goal

Let users save in-place from workflow unsaved-change confirmations rather than
canceling the confirmation and finding the relevant save action.

## Interaction

- The advanced configuration drawer shows Cancel, Discard changes, and Apply
  and close when a close or back action would discard a draft.
- The workflow designer shows Cancel, Discard changes, and Save workflow and
  continue when an action would discard graph changes.
- Saving the workflow applies a valid advanced-config draft first. On success,
  the originally requested action continues.

## Boundaries

Validation or save failure leaves all edits intact and stops the pending action.
The browser's native unload confirmation remains unchanged because it cannot
perform asynchronous application saves.

## Verification

Source-contract tests cover both dialog action sets and verify that successful
workflow save resumes the pending operation. Focused and full frontend tests,
plus a production build, validate the change.
