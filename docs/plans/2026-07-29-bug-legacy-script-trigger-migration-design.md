# Bug Legacy Script Trigger Migration

## Context

The enabled Bug workflow definition `#33` contains a historical trigger on the
"reopen to refix" transition. Its value is `{ "type": "legacy_script" }` and
does not contain a script payload or other business data. The current runtime
and designer only support notification automations. The unsupported value blocks
visual workflow saves and would also prevent runtime execution of that
transition.

Task and requirement workflows already use supported declarative configuration;
they need no graph or data changes.

## Decision

Remove the empty `legacy_script` trigger from the affected Bug transition. The
transition itself, its states, permissions, ownership rules, and action name
remain unchanged.

Add validation so unsupported automation types cannot be persisted through the
workflow-definition API, plus a migration regression test proving the cleanup is
scoped to the legacy trigger.

## Verification

Run the focused migration and workflow-definition tests, then the backend test
suite needed by the changed modules. Verify the existing workflow designer can
save the enabled Bug graph after migration.
