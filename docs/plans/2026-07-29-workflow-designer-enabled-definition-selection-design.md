# Workflow Designer Enabled Definition Selection

## Context

An assignee-rule workflow scheme can retain disabled historical definitions. The
workflow designer currently takes the first definition returned by the API. Since
the API sorts by descending ID without filtering disabled definitions, the
designer can show a disabled definition rather than the definition used by the
runtime.

For the default workflow scheme, the enabled Bug definition is `#33`, while a
higher-ID disabled definition (`#466`) was displayed in the designer. This made
the configured actions disagree with the actions shown in the workbench.

## Decision

The workflow designer will select the enabled definition from the fetched
definitions for the selected object type. It will only create a definition when
no enabled definition is present.

Historical disabled definitions remain untouched. Existing work items keep their
current workflow definition and state bindings.

## Verification

Add a source-contract regression test asserting that the designer selects an
enabled definition even when a disabled definition with a higher ID is returned
first. Run the affected frontend test and the full frontend test suite.
