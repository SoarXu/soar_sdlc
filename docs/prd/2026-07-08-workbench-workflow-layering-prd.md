# Workbench And Workflow Layering PRD

## 1. Background

The current workbench and workflow areas are difficult to maintain because page display logic, process rules, permission checks, current-handler assignment, and management actions are mixed together.

This PRD records the confirmed decisions for reorganizing the workbench and workflow configuration. Each new confirmed decision should be appended to this document to avoid losing context during later design and implementation.

## 2. Goals

- Clarify the responsibility boundary between workbench display, workflow configuration, and workflow execution.
- Define which objects appear in the workbench.
- Define state, action, permission, and current-handler rules for each object.
- Make workbench buttons derive from workflow rules instead of being hard-coded by page logic.
- Provide a stable basis for later UI, API, and permission changes.

## 2.1 Default Template Principle

Confirmed.

All statuses, transitions, actions, handler rules, and workbench behaviors confirmed in this PRD are the rules of the **default workflow templates**.

Principles:

- The default template is the baseline behavior shipped by the system.
- Later, administrators or permitted project-level configurators may extend workflow definitions.
- Extension may include:
  - Adding statuses.
  - Adding transitions.
  - Adding or disabling actions.
  - Adjusting handler-routing rules.
  - Enabling or disabling optional confirmation steps.
- Workflow extension should not invalidate the baseline permission model, audit requirements, or workbench action-derivation model.
- The default template remains the reference model for implementation, onboarding, and fallback behavior.

## 3. Confirmed Decisions

### D1. Workbench, Workflow Configuration, And Workflow Execution Boundary

Confirmed.

The system is divided into three responsibility layers:

| Layer | Responsibility |
|---|---|
| Workbench | Displays personal work, project work, exception items, and operation entry points. It is responsible for layout, filtering, sorting, grouping, and invoking available actions. |
| Workflow configuration | Defines statuses, transitions, permissions, current-handler assignment, notifications, blocking conditions, and automation rules. |
| Workflow execution | Evaluates workflow configuration when a user performs an action, validates permission and preconditions, updates status/current handler, triggers side effects, and writes audit logs. |

Rules:

- The workbench should not hard-code process transition rules.
- The workbench should request available actions for each item from the backend or workflow execution service.
- Workflow configuration is the source of truth for process rules.
- Workflow execution is the source of truth for whether the current user can perform a specific action.
- Workflow logic should not depend on page layout.

### D2. Workbench Button Derivation Rule

Confirmed.

Workbench buttons are derived from this rule:

```text
Object + Current Status + Current User Identity = Available Actions
```

Each available action must define:

- Object type.
- Current status.
- Required user identity or permission.
- Button label.
- Target status after click.
- Current-handler change after click.
- Preconditions or blocking checks.
- Button placement: primary action, secondary action, or management action.

Button categories:

| Button Type | Placement | Examples |
|---|---|---|
| Primary process action | Main row/card action | Start processing, submit for test, finish fix, verify passed |
| Secondary action | More menu or detail page | Edit, comment, link requirement, view history |
| Management action | Visible to project owner/system admin when permitted | Assign, change owner, force close, return, delete |

Principles:

- Ordinary members only see actions they can actually perform.
- Project owners can see additional assignment and correction actions.
- System administrators can see fallback and administrative actions.
- Hidden buttons are not a security boundary; backend permission checks remain authoritative.

### D2-1. Workflow Action Result-Based Routing

Confirmed.

Workflow configuration must support routing based on values selected during an action.

Example:

- The workbench shows one action: `Confirm Bug Type`.
- The user clicks the action and selects a Bug type.
- Workflow execution reads the selected type.
- Workflow configuration maps the selected type to the target status.

Default Bug example:

| Action | Selected Type Category | Target Status |
|---|---|---|
| Confirm Bug Type | Real defect, such as code issue | `Fixing` |
| Confirm Bug Type | Non-defect, such as design-as-intended | `Pending Verification` |

Rules:

- The workbench should not expose separate hard-coded buttons such as `Confirm Is Bug` and `Confirm Is Not Bug` if the decision can be derived from the selected Bug type.
- The selected value and the computed target status must be recorded in audit/history.
- Workflow configuration should define the condition mapping between action form values and target statuses.
- If no condition matches, workflow execution must block the transition and show a clear configuration error.

Workflow configuration must also support whether the handler can manually choose the target status for a given action.

Routing modes:

| Routing Mode | Meaning |
|---|---|
| Automatic | The target status is fully determined by workflow condition mapping. The user cannot manually choose the target status. |
| Manual allowed | Workflow condition mapping provides the allowed target statuses, and the user must choose one during the action. |
| Automatic with override | Workflow condition mapping provides the default target status, but permitted users can override it from an allowed target-status list. |

Rules:

- Manual target-status selection is configured per workflow action.
- The allowed target statuses must still be constrained by workflow configuration.
- The workbench cannot offer arbitrary target statuses.
- Permission to override the default target status can be limited to specific identities, such as current handler, project owner, or system admin.
- The selected target status, default target status, and override reason must be recorded in history when manual selection or override happens.

## 4. Object Confirmation Sequence

The object confirmation sequence is:

1. Bug.
2. Requirement.
3. Task.
4. Test case.
5. Test run/test sheet.
6. Iteration.
7. Project-level management actions.

## 5. Bug Workflow Confirmation

### D3. Bug Status Set

Confirmed with pending sub-decisions.

Bug does not use independent `Assigned` or `New` statuses.

Reason:

- Assignment is already represented by the Bug owner/current handler.
- Once a Bug is assigned to someone, it appears in that person's pending work list.
- `Assigned` does not represent a clear business-processing stage.
- Keeping `Assigned` would make workbench buttons ambiguous because the system still needs to decide whether the next action is start fixing, reassign, reject, or close.
- `New` only describes creation timing and does not clearly describe the work expected from the current handler.

Confirmed minimal Bug statuses:

| Status | Meaning |
|---|---|
| Pending Handling | Bug has entered the handling queue. If it has no current handler, it waits to be claimed or assigned. If it has a current handler, it appears in that handler's pending work list. The handler must confirm whether it is a real Bug and classify it. |
| Fixing | The handler has confirmed it is a real Bug and repair work is in progress. |
| Pending Verification | The Bug is waiting for verification. This can happen after repair completion, and may also happen after the handler confirms the issue is not a Bug if business requires verification of that conclusion. |
| Verified | Verification has passed, but the Bug has not been formally closed. |
| Closed | Verification passed or the Bug is confirmed as finished. Closed Bugs can be reactivated later if the same issue appears again. |

Status principles:

- Bug creation is an event, not a lifecycle status.
- `Pending Handling` covers created-with-handler, created-without-handler, claimed, assigned, and verification-failed scenarios.
- `Fixing` means the handler has confirmed the issue is a real Bug and has started repair work.
- `Pending Verification` means a tester/verifier must confirm the result.
- Verification failure returns the Bug to `Pending Handling`, not to a separate `Reopened` status.
- Reopen after close is an activation action that returns the Bug to `Pending Handling`.
- Reassignment is an action, not a status.

### D4. Bug Lifecycle

Confirmed with pending sub-decisions.

Bug lifecycle:

1. A Bug is created.
2. After creation, the Bug may have a selected handler or no handler.
3. If it has no handler, it waits to be claimed or assigned.
4. If it has a handler, either from creation, claim, or assignment, it appears in that handler's pending work list.
5. The pending handler must confirm the Bug type.
6. Bug type selection determines the next status through workflow configuration:
   - Real defect types, such as code issue, enter `Fixing`.
   - Non-defect types, such as design-as-intended, enter `Pending Verification`.
7. From `Fixing`, the handler submits it for verification and the Bug enters `Pending Verification`.
8. If the selected type is a non-defect type, the Bug enters `Pending Verification` for tester/product confirmation.
9. The selected Bug type and target status must be recorded in history.
10. In `Pending Verification`, the verifier can choose verification passed or verification failed.
11. Verification failed returns the Bug to `Pending Handling`.
12. Verification passed moves the Bug to `Verified`.
13. A separate close action moves the Bug from `Verified` to `Closed`.
14. Closed Bugs end the normal lifecycle.
15. A closed Bug can be activated later if the same problem appears again. Activation returns it to `Pending Handling`.

Open sub-decisions:

| Decision | Options | Recommended |
|---|---|---|
| D4-1. Not-Bug confirmation handling | Confirmed: enter `Pending Verification` | A |
| D4-2. Verification passed handling | Confirmed: enter `Verified`, then require a separate close action | B |

Recommendation for D4-1:

Confirmed. When the handler confirms an issue is not a Bug, it enters `Pending Verification` instead of closing directly. The original reporter, tester, product owner, or project owner should verify the conclusion. This avoids developers unilaterally closing disputed defects.

Decision for D4-2:

Confirmed. Verification passed moves the Bug to `Verified`. The Bug is closed only after a separate close action.

Reason:

- Verification and final closure are separate responsibilities.
- The verified state gives project owners or designated closers a chance to review final handling before ending the lifecycle.
- This makes the workbench able to distinguish "waiting for verification" from "verified but not formally closed".

### D5. Bug Type Classification And Default Routing

Confirmed.

When a Bug is in `Pending Handling`, the current handler uses the `Confirm Bug Type` action to select a Bug type. The selected type determines the target status through workflow configuration.

Default type classification:

| Type | Real Bug | Default Target Status |
|---|---|---|
| Code Issue | Yes | `Fixing` |
| Configuration Issue | Yes | `Fixing` |
| Data Issue | Yes | `Fixing` |
| Environment Issue | Pending judgment | `Pending Verification` |
| Requirement Issue | Pending judgment | `Pending Verification` |
| Design As Intended | No | `Pending Verification` |
| Duplicate Issue | No | `Pending Verification` |
| Cannot Reproduce | No | `Pending Verification` |
| Operation Issue | No | `Pending Verification` |

Rules:

- The type list should be configurable as a system dictionary.
- Each type should define whether it is treated as a real Bug for default workflow routing.
- Each type should define a default target status.
- Each workflow action can configure whether the handler is allowed to manually choose or override the target status.
- The default workflow template uses the mapping above.
- Project-level workflow configuration may override the default mapping if project policy differs.
- The selected Bug type, whether it is treated as a real Bug, and the target status must be recorded in Bug history.

### D5-1. Bug Type Reclassification After Fixing Starts

Confirmed.

A Bug that has already entered `Fixing` may later be found to be a different type, such as a duplicate issue or a non-defect. The system must reserve an action entry for type reclassification.

Default behavior:

| Current Status | Action | Result |
|---|---|---|
| `Fixing` | Reclassify Bug Type | Select a new Bug type and route according to workflow configuration. |

Example:

- The handler confirms the Bug as `Code Issue`, so it enters `Fixing`.
- During repair, the handler discovers it is actually a duplicate issue.
- The handler uses `Reclassify Bug Type`.
- The selected type is `Duplicate Issue`.
- Workflow configuration routes it to `Pending Verification`.

Rules:

- Reclassification must be controlled by workflow configuration.
- Reclassification must record old type, new type, old status, target status, operator, reason, and time.
- Reclassification may require a reason field.
- Project workflow configuration may restrict which roles can reclassify a Bug after fixing starts.
- The default allowed users are current handler, project owner, and system admin.
- Reclassification does not delete previous handling history.

### D6. Bug Pending Handling Actions

Confirmed.

When a Bug is in `Pending Handling`, the workbench should expose actions according to handler state and user identity.

Default action matrix:

| Scenario / User Identity | Action | Button Type | Result |
|---|---|---|---|
| Bug has no current handler, project member | Claim | Primary or secondary action | Current handler becomes the claimant. Status remains `Pending Handling`. |
| Project owner or system admin | Assign | Management action | Current handler becomes the assigned user. Status remains `Pending Handling`. |
| Current handler | Confirm Bug Type | Primary process action | User selects Bug type. Workflow configuration routes to `Fixing` or `Pending Verification`. |
| Current handler | Transfer | Secondary action | Current handler changes to selected user. Status remains `Pending Handling`. |
| Reporter or tester | Add Information | Secondary action | Adds supplemental information. Status remains `Pending Handling`. |
| Project owner or system admin | Void / Close | Management action | Ends or invalidates the Bug according to workflow configuration and audit rules. |

Rules:

- `Confirm Bug Type` is the main process action for `Pending Handling`.
- `Claim`, `Assign`, and `Transfer` are ownership actions, not status transitions.
- `Void / Close` must be controlled by workflow configuration and permission rules.
- If the Bug has no current handler, it appears in the unassigned/claimable workbench list.
- If the Bug has a current handler, it appears in that handler's pending work list.
- Workbench button visibility is derived from workflow execution permissions, not hard-coded page logic.

### D7. Bug Fixing Actions

Confirmed.

When a Bug is in `Fixing`, the workbench should expose actions according to user identity.

Default action matrix:

| User Identity | Action | Button Type | Result |
|---|---|---|---|
| Current handler | Submit Verification | Primary process action | Bug enters `Pending Verification`. Current handler changes according to verification assignment rules. |
| Current handler | Reclassify Bug Type | Secondary process action | User selects a new Bug type. Workflow configuration routes to the target status. |
| Current handler | Transfer | Secondary action | Current handler changes to selected user. Status remains `Fixing`. |
| Project owner or system admin | Assign / Change Handler | Management action | Current handler changes to assigned user. Status remains `Fixing`. |
| Project owner or system admin | Void / Close | Management action | Ends or invalidates the Bug according to workflow configuration and audit rules. |
| Reporter or tester | Add Information | Secondary action | Adds supplemental information. Status remains `Fixing`. |

Rules:

- `Submit Verification` is the main process action for `Fixing`.
- `Reclassify Bug Type` is reserved for cases where the issue is later found to be a duplicate, design-as-intended, cannot reproduce, or another non-repair type.
- `Transfer` and `Assign / Change Handler` are ownership actions, not status transitions.
- Project-level workflow configuration may restrict who can close or void a Bug while it is in `Fixing`.
- Submitting verification should require configured completion fields if enabled, such as fix description, affected version, or related code reference.

### D8. Bug Pending Verification Actions

Confirmed.

When a Bug is in `Pending Verification`, the workbench should expose verification actions according to user identity.

Default action matrix:

| User Identity | Action | Button Type | Result |
|---|---|---|---|
| Current verifier | Verification Passed | Primary process action | Bug enters `Verified`. |
| Current verifier | Verification Failed | Primary process action | Bug returns to `Pending Handling`. Current handler changes according to handling assignment rules. |
| Current verifier | Transfer Verification | Secondary action | Current handler changes to selected verifier. Status remains `Pending Verification`. |
| Project owner or system admin | Assign Verifier | Management action | Current handler changes to assigned verifier. Status remains `Pending Verification`. |
| Reporter or tester | Add Information | Secondary action | Adds supplemental information. Status remains `Pending Verification`. |
| Project owner or system admin | Void / Close | Management action | Ends or invalidates the Bug according to workflow configuration and audit rules. |

Rules:

- `Verification Passed` moves the Bug to `Verified`, not directly to `Closed`.
- `Verification Failed` returns the Bug to `Pending Handling`.
- Verification failure should require a failure reason if configured.
- Verification failure should preserve repair and verification history.
- The current handler after verification failure is determined by workflow configuration. The default should be the previous repair handler.
- `Transfer Verification` and `Assign Verifier` are ownership actions, not status transitions.

### D9. Bug Verified Actions

Confirmed.

When a Bug is in `Verified`, the workbench should expose final closure and rollback actions according to user identity.

Default action matrix:

| User Identity | Action | Button Type | Result |
|---|---|---|---|
| Current verifier | Close | Primary process action | Bug enters `Closed`. |
| Project owner or system admin | Close | Management action | Bug enters `Closed`. |
| Reporter or tester | Return / Reopen | Secondary process action | Bug returns to `Pending Handling`. |
| Project owner or system admin | Return / Reopen | Management action | Bug returns to `Pending Handling`. |
| User with view/comment permission | View History / Add Information | Secondary action | Adds supplemental information or views history. Status remains `Verified`. |

Rules:

- `Verified` means verification passed but formal closure has not happened.
- `Close` moves the Bug to `Closed`.
- Default users allowed to close a verified Bug are current verifier, project owner, and system admin.
- `Return / Reopen` from `Verified` returns the Bug to `Pending Handling`.
- Return/reopen should require a reason if configured.
- Project-level workflow configuration may restrict who can return or close a verified Bug.

### D10. Bug Closed Actions

Confirmed.

When a Bug is in `Closed`, the workbench should expose activation and history actions according to user identity.

Default action matrix:

| User Identity | Action | Button Type | Result |
|---|---|---|---|
| Reporter or tester | Activate | Primary or secondary process action | Bug returns to `Pending Handling`. |
| Project owner or system admin | Activate | Management action | Bug returns to `Pending Handling`. |
| User with view/comment permission | View History | Secondary action | Views Bug history. Status remains `Closed`. |
| User with comment permission | Add Comment | Secondary action | Adds supplemental information. Status remains `Closed`. |

Rules:

- Closed Bugs end the normal lifecycle but can be activated if the same or related issue appears again.
- Reporter and tester can directly activate a closed Bug.
- Project owner and system admin can directly activate a closed Bug.
- Activation returns the Bug to `Pending Handling`.
- Activation should require an activation reason if configured.
- Workflow configuration determines the current handler after activation. The default can be the previous repair handler, previous verifier, project owner, or empty/unassigned according to project policy.
- Activation must preserve all previous lifecycle history.

### D10-1. Bug Close Blocking Rules

Confirmed.

In the default workflow template, a Bug cannot be closed while directly related tasks are still active.

Default blocking rules for `Verified -> Closed`:

- If any directly related task is not in `Completed` or `Canceled`, block closing the Bug.

Rules:

- The default template checks all directly related tasks.
- Blocking happens during workflow execution when the user clicks `Close`.
- The Bug status must remain unchanged when blocking happens.
- The response should clearly show why closing was blocked.
- Later workflow templates may refine this rule, but the baseline default template should block on any directly related unfinished task.

### D10-2. Bug Reactivation Task Linkage Rules

Confirmed.

In the default workflow template, Bug reactivation does not automatically change the state of related tasks.

Default rules:

- Reactivating a Bug does not automatically reactivate old related tasks.
- Reactivating a Bug does not automatically create a new related task.
- Reactivating a Bug does not automatically change the state of other related objects.
- After reactivation, task handling should be decided manually by permitted users.

Manual follow-up options may include:

- Create a new related task.
- Manually reactivate an old task if the workflow and permissions allow it.
- Handle the Bug directly without creating a task.

Rules:

- The default template keeps Bug reactivation stable and non-propagating.
- This avoids silently reviving outdated execution tasks or creating unexpected new work items.
- Later workflow templates may add stronger automatic linkage, but the baseline default template should remain manual.

### D10-3. Bug Close/Void Auto-Close Task Policy

Confirmed.

In the default workflow template, Bug close/void actions should not automatically close related tasks.

Default rules:

- Closing a Bug does not automatically close directly related tasks.
- Voiding a Bug does not automatically close directly related tasks.
- Related tasks remain in their current states unless users explicitly act on them.

Optional workflow-template extension:

- A later workflow template may allow "auto-close directly related tasks when closing/voiding a Bug".
- This extension should not be enabled by default.

Mandatory safeguards when the extension is enabled:

- The system must show an explicit pre-execution prompt.
- The prompt should clearly show:
  - how many related tasks will be affected,
  - which tasks will be affected or a practical summary,
  - which target state will be applied to those tasks,
  - whether partial exclusion is supported if the template allows it.
- The system must write audit records for:
  - the triggering Bug action,
  - the affected related tasks,
  - the resulting task state changes,
  - the operator,
  - the reason or confirmation context where required.

Recommended target-state rule:

- If a workflow template later enables automatic task closure from Bug close/void, the default target state should be `Canceled`, not `Completed`, unless the template explicitly defines another business meaning.

Compatibility rule with close blocking:

- Default template mode:
  - Bug close is blocked by any directly related task that is not `Completed` or `Canceled`.
  - No automatic task closure is performed.
- Optional auto-close template mode:
  - If the workflow template enables automatic closure of directly related tasks during Bug close/void, the Bug should not be blocked by related tasks that are eligible for that automatic closure.
  - Bug close/void should still be blocked if:
    - some related tasks are not eligible for auto-close,
    - some related tasks are in states excluded from auto-close,
    - the operator lacks permission for the linked task action,
    - required confirmation/prompt is not accepted,
    - linked auto-close execution fails.

Design principle:

- Blocking mode and automatic linked-closure mode must not contradict each other.
- The system should behave in one coherent mode for the configured template, not both at once.

### D11. Bug Current Handler Principles

Confirmed.

Bug current-handler assignment must distinguish repair handling from verification handling.

Core principles:

- Bug confirmation is performed by the repair handler, usually a developer or a person assigned by the project owner.
- Test case execution is performed by the tester.
- If a Bug is created from test execution, the tester is the reporter/source executor, not the default Bug confirmation handler.
- The Bug should enter the repair handler's pending work list only after a repair handler is selected, assigned, claimed, or derived by workflow configuration.
- Verification work should return to the tester, reporter, or configured verifier after repair submission or non-defect confirmation.

Default current-handler rules:

| Scenario | Current Handler |
|---|---|
| Bug is created with a selected repair handler | Selected repair handler. |
| Bug is created without a repair handler | Empty. The Bug appears in the unassigned/claimable workbench list. |
| Bug is created from test execution | The system first derives the repair handler from the related task or requirement owner. If no handler can be derived, current handler remains empty and the Bug appears in the unassigned/claimable workbench list. The test executor is not automatically the repair handler. |
| Claim | Claimant. |
| Assign / transfer | Assigned user. |
| Confirm Bug type and enter `Fixing` | Current repair handler remains unchanged. |
| Confirm Bug type and enter `Pending Verification` | Current handler changes to the configured verifier. Default verifier can be reporter, test executor, or project owner according to workflow configuration. |
| Submit verification from `Fixing` | Current handler changes to the configured verifier. Default verifier should be the test executor when the Bug comes from test execution; otherwise reporter or configured tester. |
| Verification failed | Current handler changes to the previous repair handler by default. |
| Verification passed and enter `Verified` | Current handler can remain the verifier or change to the configured closer according to workflow configuration. |
| Close | Current handler is cleared or set to the closer according to workflow configuration. |
| Activate from `Closed` | Current handler is assigned by workflow configuration. Default can be previous repair handler or empty. |

Rules:

- Workbench pending lists are driven by current handler plus status.
- The same person can be both reporter and repair handler only if explicitly selected, assigned, claimed, or derived by configuration.
- Workflow configuration should define default verifier selection for each Bug source.
- For Bugs created from test execution, the default repair-handler derivation order is related task owner first, then related requirement owner, then empty/unassigned.
- Default verifier selection order:
  1. If the Bug comes from test execution, use the original test executor.
  2. If the Bug is linked to a test case but has no executor, use the test case's default tester.
  3. If the Bug was submitted manually, use the Bug reporter.
  4. If the reporter cannot verify or is not suitable, use the project owner or project default test owner.
  5. If the project configures a fixed verifier, use the configured verifier according to workflow priority.
- Source information, such as test execution record, test case, reporter, and original repair handler, must be preserved for later assignment decisions.

## 6. Pending Decisions

- Confirm Bug action matrix.
- Confirm ambiguous Bug type handling, especially Environment Issue and Requirement Issue.
- Confirm Bug current-handler assignment rules.
- Confirm Bug permission rules.
- Confirm Bug exception rules for leader/admin workbench.
- Confirm workbench view structure.
- Confirm watch/follow and mention implementation details.
- Confirm requirement workflow and buttons.
- Confirm task lifecycle branches, statuses, and buttons.
- Confirm test workflow and buttons.
- Confirm final workbench view structure.

## 6. Workbench View Confirmation

### D12. Workbench View Naming And Scope

Confirmed.

Workbench views should use clear business names:

| View | Definition |
|---|---|
| Pending Handling | Items whose current handler is the current user. |
| Unassigned | Items with empty current handler that need to be claimed or assigned. |
| Created / Watched | Items created by the current user, manually watched by the current user, or where the current user was mentioned. |
| Project Board | Items grouped by project, iteration, status, owner, and handler. |
| Exception Center | Overdue, unassigned, verification failed, repeatedly activated, or long-unclosed items. |

Naming in the Chinese UI:

| English Name | Chinese Name |
|---|---|
| Pending Handling | 待处理 |
| Unassigned | 未分派 |
| Created / Watched | 我发起/关注 |
| Project Board | 项目看板 |
| Exception Center | 异常中心 |

Rules:

- `Pending Handling` is driven by current handler.
- `Unassigned` is driven by empty current handler.
- `Created / Watched` must have explicit inclusion rules and should not include every item the user has ever processed by default.
- `Created / Watched` should be split into internal tabs:
  - `Created By Me`: items created or submitted by the current user.
  - `Watched By Me`: items manually watched by the current user.
  - `Mentioned Me`: items where the current user was mentioned in comments.
- The Chinese UI labels are:
  - `我发起的`
  - `我关注的`
  - `提到我的`

### D13. Watch And Mention Implementation

Confirmed.

`Created / Watched` includes:

| Source | Inclusion Rule |
|---|---|
| Created | The current user created or submitted the item. |
| Manual watch | The current user clicked watch/follow on the item. |
| Mention | The current user was mentioned in a comment. |

Manual watch:

- Core object detail pages and list rows should provide `Watch` / `Unwatch`.
- Applicable first-version objects: requirement, task, Bug, test sheet, and iteration if needed.
- Project watch can be deferred unless there is a clear need.

Mention:

- Mentions are first implemented in comments.
- When the user types `@` in a comment input, the frontend must open a user selector.
- The user must select from the user list; plain text matching is not enough because names can duplicate.
- The saved comment should store mentioned user IDs, not only display names.
- After saving the comment, the system creates notifications for mentioned users.
- Mentioned users are automatically added to watch/follow scope for that object with source `mention`.
- Mentioned users continuously watch the item by default after being mentioned.
- Mentioned users can later cancel watching the item, but the historical notification remains.

Suggested data structure:

```text
object_watch
```

| Field | Meaning |
|---|---|
| user_id | Watcher. |
| object_type | Object type, such as bug, requirement, or task. |
| object_id | Object ID. |
| source | Watch source: manual, mention, created, system. |
| enabled | Whether the watch is active. |
| created_at | Created time. |

Rules:

- One active watch record should exist per user/object/source policy, or the service should merge sources into one effective watch relation.
- Canceling manual watch should not delete the historical mention/comment/notification.
- Canceling watch after being mentioned stops future watch-based tracking but does not delete the historical mention notification.
- The comment display should show user names, while the persisted mention relation should use user IDs.
- Mention parsing and object watch creation should happen on the backend when saving comments.

### D14. Exception Center Scope

Confirmed.

The first version of the workbench exception center should include the following exception types:

| Exception Type | Meaning |
|---|---|
| Unassigned Timeout | Current handler is empty for longer than the configured threshold. |
| Pending Handling Timeout | Item has a current handler but remains unprocessed for longer than the configured threshold. |
| Fixing Timeout | Bug or task remains in fixing/processing status for longer than the configured threshold. |
| Pending Verification Timeout | Item remains in pending verification for longer than the configured threshold. |
| Verified Not Closed | Item is verified but not formally closed for longer than the configured threshold. |
| Verification Failed | Item was returned after failed verification. |
| Repeated Activation | Closed item has been activated multiple times. |
| High Priority Unprocessed | High or urgent item is not handled within the configured threshold. |

Rules:

- Exception thresholds should be configurable by object type, project, priority, and status where needed.
- Exception center should support filtering by project, object type, priority, status, handler, owner, and overdue duration.
- Leaders and system administrators should be able to view cross-project exceptions according to permission boundaries.
- Project owners should see exceptions in their own projects.
- Ordinary users should see exceptions related to items they handle, created, watch, or are permitted to view.
- Exceptions should link to the object detail page and show the current available actions from workflow execution.

### D15. Workbench Navigation Order

Confirmed.

Workbench main entries should use the following order:

1. Pending Handling / 待处理.
2. Unassigned / 未分派.
3. Exception Center / 异常中心.
4. Created / Watched / 我发起/关注.
5. Project Board / 项目看板.

Reason:

- Daily processing comes first.
- Unassigned work should be visible early to avoid lost work.
- Exceptions and risk are more urgent than passive tracking.
- Created/watched items are primarily for follow-up.
- Project board is a broader management and overview entry.

## 7. Task Workflow Confirmation

### D16. Task Positioning Principles

Confirmed.

Task is not limited to a developer-created child object under a requirement.

Confirmed principles:

- A task may be created by developer, tester, product owner, project owner, or other permitted project members according to permission rules.
- A task may be created from a requirement, but it may also be created independently without a requirement.
- A task workflow should not assume a single fixed source.
- A task workflow should support multi-branch lifecycle routing instead of a single linear path.

Implications:

- Task workflow must distinguish source context, such as requirement-derived, bug-derived, test-derived, project-operation, or standalone.
- Different task types may share a common core lifecycle but branch differently based on task type, source, or selected handling mode.
- Task workbench actions must be generated from workflow configuration, not from the assumption that every task is a developer-owned execution item.

### D17. Task Primary Branches

Confirmed.

Task workflow should first branch by task source/nature.

Primary branches:

| Branch | Meaning |
|---|---|
| Requirement Implementation | Task created for implementing a requirement or requirement change. |
| Defect Fix | Task created for handling a Bug or defect-related repair work. |
| Test Support | Task created for testing support work, such as test data preparation, environment setup, script preparation, or verification support. |
| Standalone Operation | Task created independently for project operation, coordination, cleanup, analysis, migration, or other standalone work. |

Rules:

- Branch type should be selected explicitly at creation time or derived from source object when applicable.
- Workflow configuration may provide different transition branches, required fields, handler rules, and verification rules for different task branches.
- Different task branches should still reuse one common task object model unless later evidence requires separate object types.

### D18. Task State Pool Strategy

Confirmed.

Task should use a shared state pool, but different task branches and workflow templates may use different paths through that pool.

Confirmed principles:

- Task should use `Completed` instead of `Closed` as the terminal success state.
- A task without a handler should not be in `In Processing`.
- Task should use `Pending Assignment` before a handler is assigned.
- Task should use `In Processing` after a handler is assigned, claimed, or otherwise determined.
- Not every task must pass through a confirmation state.
- Whether a task needs confirmation should be determined by task branch and workflow template.
- A developer self-managed task created from a requirement can finish directly after execution without a separate confirmation step.
- Assigning a handler is an ownership action, not a status transition.
  - Exception: for tasks in `Pending Assignment`, assigning or claiming a handler changes the task into `In Processing`.

Recommended shared task state pool:

| State | Meaning |
|---|---|
| Pending Assignment | Task has been created but has no current handler yet. |
| In Processing | Task has a current handler and has entered the execution lifecycle. It has not yet reached confirmation, completion, or cancellation. |
| Pending Confirmation | Task result has been submitted and is waiting for verification, confirmation, or acceptance. This state is optional depending on workflow template. |
| Completed | Task has finished successfully. |
| Canceled | Task is no longer executed. |

Default branch examples:

| Branch | Suggested Path |
|---|---|
| Requirement implementation, developer self-managed | `Pending Assignment/In Processing -> Completed` |
| Defect fix task | `Pending Assignment/In Processing -> Pending Confirmation -> Completed` |
| Test support task | `Pending Assignment/In Processing -> Pending Confirmation -> Completed` |
| Standalone operation task | `Pending Assignment/In Processing -> Completed`, with optional `Pending Confirmation` when needed |

Rules:

- `Pending Confirmation` is an optional workflow state, not a mandatory state for all tasks.
- `Completed` is the normal terminal state for successful task execution.
- `Canceled` is used when the task is no longer needed, replaced, merged, or intentionally not executed.
- Task workflow configuration should decide which branches can skip `Pending Confirmation`.
- A task can be created with a handler or without a handler.
- If it has no handler, it should be in `Pending Assignment` and appear in the `Unassigned` workbench view.
- If it is created with a handler, it enters `In Processing`.
- If a task gets a handler later through assignment or claim, it changes from `Pending Assignment` to `In Processing` and moves into that handler's `Pending Handling / 待处理` workbench list.

### D19. Task Branch Default Confirmation Rules

Confirmed.

Different task branches use different default completion paths.

Default rules:

| Task Branch | Default Needs `Pending Confirmation` | Default Path |
|---|---|---|
| Requirement Implementation | No | `In Processing -> Completed` |
| Defect Fix | Yes | `In Processing -> Pending Confirmation -> Completed` |
| Test Support | Yes | `In Processing -> Pending Confirmation -> Completed` |
| Standalone Operation | Configurable, default No | `In Processing -> Completed` |

Rules:

- `Pending Confirmation` is optional for task workflow and is enabled by branch/template policy.
- Requirement implementation tasks are self-managed by default and do not require an extra confirmation state unless the project workflow explicitly enables it.
- Defect-fix tasks and test-support tasks require confirmation by default because they usually produce output that another role or responsible party should review.
- Standalone operation tasks default to direct completion, but projects may enable `Pending Confirmation` for stronger control.

### D20. Task Pending Assignment Actions

Confirmed.

When a task is in `Pending Assignment`, the workbench should expose actions according to user identity.

Default action matrix:

| User Identity | Action | Button Type | Result |
|---|---|---|---|
| Project member | Claim | Primary or secondary process action | Current handler becomes the claimant. Task enters `In Processing`. |
| Project owner or system admin | Assign | Management action | Current handler becomes the assigned user. Task enters `In Processing`. |
| Creator | Edit | Secondary action | Updates task content. Status remains `Pending Assignment`. |
| Creator, project owner, or system admin | Cancel | Management or secondary process action | Task enters `Canceled`. |
| Watcher or related user with permission | Add Information | Secondary action | Adds supplemental information. Status remains `Pending Assignment`. |

Rules:

- `Claim` and `Assign` both transition the task from `Pending Assignment` to `In Processing`.
- `Edit` and `Add Information` do not change task status.
- `Cancel` should require permission checks and follow workflow audit rules.
- If project policy forbids free claiming for some task templates, `Claim` can be disabled by workflow configuration.

### D21. Task In Processing Actions

Confirmed.

When a task is in `In Processing`, the workbench should expose actions according to workflow template and user identity.

Default action matrix:

| User Identity | Action | Button Type | Result |
|---|---|---|---|
| Current handler | Complete | Primary process action | For templates that do not require confirmation, task enters `Completed`. |
| Current handler | Submit Confirmation | Primary process action | For templates that require confirmation, task enters `Pending Confirmation`. |
| Current handler | Transfer | Secondary action | Current handler changes to selected user. Status remains `In Processing`. |
| Project owner or system admin | Assign / Change Handler | Management action | Current handler changes to assigned user. Status remains `In Processing`. |
| Creator, watcher, or related user with permission | Add Information | Secondary action | Adds supplemental information. Status remains `In Processing`. |
| Current handler, project owner, or system admin | Cancel | Management or secondary process action | Task enters `Canceled`. |

Rules:

- Templates that do not require confirmation should expose `Complete`.
- Templates that require confirmation should expose `Submit Confirmation`.
- `Transfer` and `Assign / Change Handler` are ownership actions, not status transitions.
- `Cancel` should require permission checks and follow workflow audit rules.
- Workflow configuration may require completion notes, output links, attachments, or result fields before `Complete` or `Submit Confirmation`.

### D21-1. When To Create Tasks From Bugs

Confirmed.

Not every Bug should create a task. A Bug-linked task is created only when Bug handling needs a separate execution item for assignment, tracking, decomposition, or confirmation.

Typical scenarios:

| Scenario | Why create a Bug-linked task |
|---|---|
| Bug handling must be assigned to a specific executor | The Bug owner is not the actual executor. |
| A Bug requires multiple execution steps | For example data repair, configuration change, code change, deployment, or separate verification preparation. |
| Bug handling requires cross-role coordination | For example developer, tester, operations, or product collaboration. |
| The Bug is only the problem entry, and execution needs a separate trackable unit | Execution progress should be tracked independently from the Bug lifecycle. |
| The project needs finer-grained delivery tracking for Bug handling | Task completion and confirmation are tracked separately. |

Typical non-scenarios:

| Scenario | Why not create a Bug-linked task |
|---|---|
| The assigned developer can repair directly within the Bug lifecycle | The Bug itself is enough for tracking. |
| The repair is very small and needs no further assignment or decomposition | A separate task only adds management overhead. |
| The issue is classified as non-Bug and has no execution work | No repair task is needed. |

Default creation strategy:

- Default mode: manual creation on demand.
- Optional enhancement: workflow configuration may suggest task creation for certain Bug types.
- Optional enhancement: specific project templates may auto-create default Bug-fix tasks.

Rules:

- A Bug-linked task should preserve the relation to the source Bug.
- The Bug lifecycle and the task lifecycle are related but not identical.
- Completion of a Bug-linked task does not automatically mean the Bug is closed unless workflow configuration explicitly defines that linkage.

### D22. Linked Task Creation Permission And Default Handler Rules

Confirmed.

When a task is created from another object such as a requirement, Bug, or test-related object, the system should apply detailed default-handler and permission rules.

#### D22-1. Default Handler Rule

- The default handler of a linked task should be the current handler of the source object.
- Examples:
  - Creating a task from a requirement: default handler is the current handler of the requirement.
  - Creating a task from a Bug: default handler is the current handler of the Bug.
  - Creating a task from a test-related object: default handler is the current handler of that source object.
- Reason:
  - The current handler is the person currently responsible for advancing the source object.
  - That person is the most reasonable default owner for any newly split execution task derived from the source object.

#### D22-2. Who Can Create Linked Tasks

- The following identities can create linked tasks by default:
  - Current handler of the source object.
  - Project owner.
  - System admin.
- Other project members should not create linked tasks by default.
- Workflow template or project configuration may explicitly allow additional roles to create linked tasks where needed.

#### D22-3. Why Creation Is Not Limited To Current Handler Only

- Linked task creation should not be limited only to the current handler.
- Reason:
  - Project owners often need to intervene, split work, and coordinate execution during delays, personnel changes, or cross-role handling.
  - System administrators may need operational fallback authority for exceptional cases.
  - Restricting creation only to the current handler would block normal management intervention in real project scenarios.

#### D22-4. When A Non-Current-Handler Creates The Linked Task

- If a project owner or system admin creates a linked task from a source object:
  - The new task should still default its handler from the current handler of the source object.
  - The creator may change the task handler if they have permission to do so.
- This preserves the normal ownership chain while allowing management-side correction when needed.

#### D22-5. When The Source Object Has No Current Handler

- If the source object has no current handler:
  - The linked task should default to no handler.
  - The task enters `Pending Assignment`.
  - The task appears in the `Unassigned / 未分派` workbench view.
- Workflow template may optionally require the creator to select a handler before creation completes.

#### D22-6. Relationship Between Source Object Handler And New Task Handler

- Source-object current handler is the default, not an irreversible lock.
- The new task handler may be changed by:
  - The creator, if they have assignment permission.
  - Project owner.
  - System admin.
  - Workflow rules that derive another handler from source context.
- This means the default inheritance is strong enough to reduce manual work, but still flexible enough for coordination and reassignment.

#### D22-7. Audit And Traceability Requirements

- The system should record:
  - Source object type.
  - Source object ID.
  - Linked task creator.
  - Whether the creator is the current handler, project owner, or system admin.
  - Default inherited handler.
  - Final selected handler.
  - Whether the handler was manually changed during creation.
- This history is needed to explain why the task entered a certain person's queue and how management intervention happened.

#### D22-8. Recommended Default Rule Summary

- Linked task default handler = source object current handler.
- Linked task creators by default = source current handler, project owner, system admin.
- Non-current-handler creators may create linked tasks, but the handler still defaults from the source object unless changed with permission.
- If the source object has no current handler, the linked task enters `Pending Assignment`.
- Workflow templates may refine the rule, but should not silently bypass audit and permission control.

### D23. Task Confirmation Handler Rules

Confirmed.

When a task submits for confirmation, the current handler should switch from the execution handler to the confirmation handler.

#### D23-1. Core Principle

- `Submit Confirmation` changes the task from execution ownership to confirmation ownership.
- After the task enters `Pending Confirmation`, the task should appear in the confirmation handler's `Pending Handling / 待处理` workbench view.
- The original execution handler remains part of task history and relation context, but is no longer the current handler unless the task is later returned.

#### D23-2. Confirmation Handler Source

- The confirmation handler source should be configurable in the workflow template.
- Supported confirmation-handler sources should include:
  - Task creator.
  - Source object owner.
  - Source requirement current handler or owner.
  - Source Bug reporter.
  - Source Bug verifier.
  - Source test executor.
  - Project owner.
  - Fixed user.
  - Fixed role.
  - Manual selection during submit-confirmation action.
- If the selected source cannot resolve a valid user, the rule should fall back according to configured fallback order.

#### D23-3. Default Confirmation Handler By Task Branch

| Task Branch | Default Confirmation Handler |
|---|---|
| Requirement Implementation | Requirement owner. |
| Defect Fix | Source Bug reporter or verifier. |
| Test Support | Test owner or initiator. |
| Standalone Operation | Task creator or project owner. |
| Fallback | Project owner. |

#### D23-4. Branch-Specific Meaning

- Requirement implementation task:
  - Confirmation is usually performed by the requirement owner because they can judge whether the intended work output is complete.
- Defect-fix task:
  - Confirmation is usually performed by the source Bug reporter or verifier because they are responsible for confirming the fix effect.
- Test-support task:
  - Confirmation is usually performed by the testing side, such as the test owner or task initiator.
- Standalone operation task:
  - Confirmation is usually performed by the task creator or project owner because the work often serves coordination or management objectives.

#### D23-5. Manual Confirmation-Handler Selection

- Workflow templates may allow manual confirmation-handler selection during `Submit Confirmation`.
- If manual selection is allowed:
  - The allowed confirmation-handler range must still be constrained by workflow configuration.
  - The selected user and selection reason should be recorded in history when required.

#### D23-6. Fallback Rules

- If the configured confirmation-handler source cannot resolve a user:
  - The system should follow the configured fallback chain.
  - The default final fallback should be the project owner.
- Workflow execution should not silently leave a `Pending Confirmation` task without a current handler unless the template explicitly allows an unassigned confirmation queue.

#### D23-7. Audit Requirements

- The system should record:
  - Execution handler before submit-confirmation.
  - Confirmation-handler source rule.
  - Resolved default confirmation handler.
  - Final confirmation handler.
  - Whether manual override was used.
  - Override reason where required.

#### D23-8. Recommended Default Summary

- Submit confirmation switches current handler to the confirmation handler.
- Confirmation-handler source is configured by workflow template.
- Default by branch:
  - Requirement implementation -> requirement owner.
  - Defect fix -> source Bug reporter or verifier.
  - Test support -> test owner or initiator.
- Standalone operation -> creator or project owner.
- Final fallback -> project owner.

### D24. Task Pending Confirmation Actions

Confirmed.

When a task is in `Pending Confirmation`, the workbench should expose confirmation actions according to user identity.

Default action matrix:

| User Identity | Action | Button Type | Result |
|---|---|---|---|
| Current confirmation handler | Approve / Confirm Passed | Primary process action | Task enters `Completed`. |
| Current confirmation handler | Return For Rework | Primary or secondary process action | Task returns to `In Processing`. Current handler changes according to return rules. |
| Current confirmation handler | Transfer Confirmation | Secondary action | Current handler changes to selected confirmation handler. Status remains `Pending Confirmation`. |
| Project owner or system admin | Assign / Change Confirmation Handler | Management action | Current handler changes to assigned confirmation handler. Status remains `Pending Confirmation`. |
| Creator, watcher, or related user with permission | Add Information | Secondary action | Adds supplemental information. Status remains `Pending Confirmation`. |
| Project owner or system admin | Cancel | Management or secondary process action | Task enters `Canceled`. |

Rules:

- `Approve / Confirm Passed` moves the task to `Completed`.
- `Return For Rework` moves the task back to `In Processing`.
- The default return target handler should be the previous execution handler unless workflow configuration defines another rule.
- `Transfer Confirmation` and `Assign / Change Confirmation Handler` are ownership actions, not status transitions.
- `Cancel` should require permission checks and follow workflow audit rules.
- Workflow configuration may require a return reason when sending the task back for rework.

### D24-1. Task Completion Blocking Principles

Confirmed.

Task is a lower-level execution object. In the default workflow template, task completion should be blocked only by the task's own completion conditions, not by the completion state of upper-level related objects.

Default principles:

- A task cannot be completed or submitted for confirmation if its own required completion conditions are not satisfied.
- A task should not be blocked only because:
  - the related requirement is not completed,
  - the related Bug is not closed,
  - the source object is still in progress,
  - sibling tasks are not completed.

Typical self-blocking conditions:

- The task is still in `Pending Assignment` and has no current handler.
- The workflow template requires a confirmation step, but there is no confirmation handler when `Submit Confirmation` is attempted.
- The workflow template requires result notes, output links, attachments, or required result fields, but they are missing.

Rules:

- Upper-level objects may be blocked by unfinished tasks, but tasks are not blocked by unfinished upper-level objects by default.
- Task completion may still show related-object warnings, but those should be warnings rather than blockers in the default template.
- Later workflow templates may add stronger constraints if a project truly needs them, but the baseline template should keep task completion local to the task itself.

### D24-2. Task Cancel Blocking And Linkage Principles

Confirmed.

In the default workflow template, task cancellation should remain local to the task itself and should not be blocked only by upper-level object state.

Default principles:

- Task cancellation should not be blocked only because:
  - the related requirement is not completed,
  - the related Bug is not closed,
  - the source object is still in progress,
  - sibling tasks are still active.
- Task cancellation should be blocked only by task-local workflow rules where configured.

Typical local blocking conditions:

- The task is in `Pending Confirmation` and the workflow template does not allow direct cancellation from that state.
- The workflow template requires a cancel reason, but no reason is provided.

Default linkage behavior:

- Canceling a task does not automatically cancel the related requirement.
- Canceling a task does not automatically close or cancel the related Bug.
- Canceling a task does not automatically cancel sibling tasks.
- The system may show a warning if the task is the only execution task linked to a Bug or another important source object.

Rules:

- The default template keeps task cancellation local and non-propagating.
- Warnings may be shown for coordination risk, but default behavior should avoid hidden side effects on related objects.
- Later workflow templates may enable stronger linkage, but the baseline template should remain explicit and predictable.

### D24-3. Task Completion Linkage Principles

Confirmed.

In the default workflow template, task completion does not automatically drive state transitions of upper-level or related objects.

Default principles:

- Completing a task does not automatically complete a related requirement.
- Completing a task does not automatically close or move a related Bug.
- Completing a task does not automatically complete an iteration.
- Completing a task does not automatically complete sibling tasks or related objects.

Effect on related objects:

- Task completion only removes that task from the blocking conditions checked by upper-level objects.
- Upper-level objects may later become eligible for completion because the task is no longer unfinished.
- This is a passive release of blocking conditions, not an automatic linked transition.

Rules:

- The default template should not show extra "ready for verification" or similar prompts just because a related task is completed.
- The default template should avoid hidden side effects and implicit state coupling on completion.
- Later workflow templates may add stronger linkage rules, but the baseline template should remain non-propagating.

## 8. Requirement Workflow Confirmation

### D25. Requirement Confirmation Scope

Confirmed.

Requirement discussion in this PRD is intentionally limited to status set and transition rules.

Out of scope for this confirmation round:

- Requirement business scope definition.
- Requirement decomposition strategy.
- Whether users must create tasks from requirements.
- Requirement ownership semantics beyond what is needed for status transitions.
- Requirement detail model and extended fields.

In scope for this confirmation round:

- Requirement statuses.
- Requirement transition paths.
- Requirement workflow branching rules where needed.
- Requirement workbench buttons derived from status transitions.
- Requirement current-handler changes only where needed to support status flow.

### D26. Requirement State Pool Strategy

Confirmed.

Requirement status design follows the same ownership principle used for tasks:

- If a requirement has no current handler, it should not be treated as being processed.
- Once a requirement has a current handler, it is considered `In Processing`.

Confirmed requirement state pool:

| State | Meaning |
|---|---|
| Pending Assignment | Requirement exists but has no current handler yet. |
| In Processing | Requirement has a current handler and is actively in the handling lifecycle. |
| Pending Confirmation | Requirement result has been submitted and is waiting for confirmation. |
| Completed | Requirement has been confirmed as completed. |
| Canceled | Requirement is no longer continued. |

Rules:

- A requirement without a current handler stays in `Pending Assignment`.
- Assigning or claiming a requirement changes it from `Pending Assignment` to `In Processing`.
- A requirement with a current handler is treated as `In Processing`; there is no separate `Pending Handling` state in the first version.
- `Pending Confirmation` is not part of the default requirement path and is used only when a special workflow template explicitly enables an extra confirmation step.
- `Completed` is the successful terminal state.
- `Canceled` is used when the requirement is intentionally stopped or invalidated.

### D27. Requirement Default Completion Path

Confirmed.

Requirement does not need `Pending Confirmation` by default.

Default path:

```text
Pending Assignment -> In Processing -> Completed
```

Optional path:

```text
Pending Assignment -> In Processing -> Pending Confirmation -> Completed
```

Rules:

- The default requirement template should allow direct completion from `In Processing` to `Completed`.
- `Pending Confirmation` is an optional enhancement for projects that need stronger review or acceptance control.
- If a project does not explicitly enable a confirmation step, requirement workbench actions should not expose `Submit Confirmation`.

### D28. Requirement Pending Assignment Actions

Confirmed.

When a requirement is in `Pending Assignment`, the workbench should expose actions according to user identity.

Default action matrix:

| User Identity | Action | Button Type | Result |
|---|---|---|---|
| Project member | Claim | Primary or secondary process action | Current handler becomes the claimant. Requirement enters `In Processing`. |
| Project owner or system admin | Assign | Management action | Current handler becomes the assigned user. Requirement enters `In Processing`. |
| Creator | Edit | Secondary action | Updates requirement content. Status remains `Pending Assignment`. |
| Creator, project owner, or system admin | Cancel | Management or secondary process action | Requirement enters `Canceled`. |
| Related user with permission | Add Information | Secondary action | Adds supplemental information. Status remains `Pending Assignment`. |

Rules:

- `Claim` and `Assign` both transition the requirement from `Pending Assignment` to `In Processing`.
- `Edit` and `Add Information` do not change requirement status.
- `Cancel` should require permission checks and follow workflow audit rules.
- These are default-template rules; later workflow templates may add statuses or transitions while preserving baseline permission and audit principles.

### D29. Requirement Cancel And Reactivate Rules

Confirmed.

Requirement cancellation ends the current active lifecycle without deleting the requirement.

Default rules:

- `Pending Assignment -> Canceled`
- `In Processing -> Canceled`
- `Pending Confirmation -> Canceled` when a project template explicitly enables `Pending Confirmation`

Meaning of `Canceled`:

- The requirement is no longer actively progressed in the current lifecycle.
- The requirement is not considered completed.
- The requirement is not deleted.
- History, comments, relations, and audit records must be preserved.

Reactivation:

- A canceled requirement should support `Reactivate`.
- Reactivation returns the requirement to the active lifecycle.
- If no current handler is restored or selected, reactivation returns the requirement to `Pending Assignment`.
- If a current handler is restored or selected during reactivation, the requirement returns to `In Processing`.

Rules:

- Workflow configuration may require a cancel reason and a reactivate reason.
- Reactivation should preserve the previous lifecycle history instead of creating a brand-new requirement record.
- Default-template workbench and workflow rules should treat `Canceled` as a terminal but reactivatable state.

### D29-1. Requirement Cancel Blocking Rules

Confirmed.

In the default workflow template, requirement cancellation is blocked when directly related active tasks or Bugs still exist.

Default blocking rules for cancel:

- If any directly related task is not in `Completed` or `Canceled`, block cancellation.
- If any directly related Bug is not in `Closed`, block cancellation.

Rules:

- The default template does not automatically cancel related tasks.
- The default template does not automatically close related Bugs.
- Blocking should happen during workflow execution when the user clicks `Cancel`.
- The requirement status must remain unchanged when blocking happens.
- The response should clearly show why cancellation was blocked.
- Later workflow templates may extend this behavior, such as allowing a guided bulk-cancel flow, but the default template should block first.

### D30. Requirement In Processing Actions

Confirmed.

When a requirement is in `In Processing`, the workbench should expose actions according to workflow template and user identity.

Default action matrix:

| User Identity | Action | Button Type | Result |
|---|---|---|---|
| Current handler | Complete | Primary process action | For the default requirement template, requirement enters `Completed`. |
| Current handler | Submit Confirmation | Primary process action | Only shown when a project workflow template explicitly enables `Pending Confirmation`. Requirement enters `Pending Confirmation`. |
| Current handler | Transfer | Secondary action | Current handler changes to selected user. Status remains `In Processing`. |
| Project owner or system admin | Assign / Change Handler | Management action | Current handler changes to assigned user. Status remains `In Processing`. |
| Creator or related user with permission | Add Information | Secondary action | Adds supplemental information. Status remains `In Processing`. |
| Current handler, project owner, or system admin | Cancel | Management or secondary process action | Requirement enters `Canceled`. |

Rules:

- The default requirement template should expose `Complete`, not `Submit Confirmation`.
- `Submit Confirmation` is available only when a non-default workflow template explicitly enables a confirmation step.
- `Transfer` and `Assign / Change Handler` are ownership actions, not status transitions.
- `Cancel` should require permission checks and follow workflow audit rules.

### D30-1. Requirement Completion Blocking Rules

Confirmed.

In the default workflow template, a requirement cannot be completed if directly related tasks or Bugs are not closed out.

Default blocking rules for `In Processing -> Completed`:

- If any directly related task is not in `Completed` or `Canceled`, block completion.
- If any directly related Bug is not in `Closed`, block completion.

Rules:

- Only directly related tasks and directly related Bugs are checked by the default template.
- The default template does not distinguish Bug severity for this blocking rule.
- Blocking should happen during workflow execution when the user clicks `Complete`.
- The requirement status must remain unchanged when blocking happens.
- The response should clearly show why completion was blocked, including the count or list of blocking related objects where practical.
- Later workflow templates may relax or refine this rule through workflow configuration, such as severity-based Bug checks or warning-only checks.

### D30-2. Completed Requirement Reopening Policy

Confirmed.

In the default workflow template, a completed requirement should not automatically return to `In Processing` only because new directly related Bugs appear later or old Bugs are reactivated.

Default rules:

- If a new directly related Bug is created after the requirement is completed, the requirement remains `Completed`.
- If a directly related Bug is reactivated after the requirement is completed, the requirement remains `Completed`.
- The system should surface this situation in the `Exception Center / 异常中心`.
- Relevant users may manually reactivate the requirement if they decide the requirement lifecycle should reopen.

Rules:

- The default template should avoid automatic parent-status rollback in this scenario.
- Exception records should make the linkage visible, such as "completed requirement has active related Bug".
- Manual reactivation remains the control point for returning the requirement to the active lifecycle.
- Later workflow templates may implement stronger automatic linkage, but the default template should remain stable and non-oscillating.

### D31. Requirement Canceled Actions

Confirmed.

When a requirement is in `Canceled`, the workbench should expose reactivation and history actions according to user identity.

Default action matrix:

| User Identity | Action | Button Type | Result |
|---|---|---|---|
| Creator, project owner, or system admin | Reactivate | Primary or management process action | Requirement returns to `Pending Assignment` or `In Processing` according to handler restoration/selection rules. |
| User with view/comment permission | View History | Secondary action | Views requirement history. Status remains `Canceled`. |
| User with comment permission | Add Comment / Add Information | Secondary action | Adds supplemental information. Status remains `Canceled`. |

Rules:

- `Reactivate` returns the requirement to the active lifecycle.
- If no current handler is restored or selected, reactivation moves the requirement to `Pending Assignment`.
- If a current handler is restored or selected, reactivation moves the requirement to `In Processing`.
- Workflow configuration may require a reactivate reason.

## 7. Change Log

| Date | Change |
|---|---|
| 2026-07-08 | Created PRD and recorded confirmed D1/D2 decisions. |
| 2026-07-08 | Updated D3/D4: Bug status set now follows lifecycle with Pending Handling/Fixing/Pending Verification/Verified/Closed. |
| 2026-07-08 | Confirmed D4-1: Not-Bug confirmation enters Pending Verification. |
| 2026-07-08 | Confirmed D4-2: Verification passed enters Verified, then a separate close action closes the Bug. |
| 2026-07-08 | Confirmed D2-1: workflow actions can route to different target statuses based on selected action values, such as Bug type. |
| 2026-07-08 | Confirmed D5: Bug type classification and default routing. |
| 2026-07-08 | Confirmed D2-1 extension: workflow action configuration controls whether users can manually choose or override target status. |
| 2026-07-08 | Confirmed D5-1: Bugs in Fixing can be reclassified and routed again by workflow configuration. |
| 2026-07-08 | Confirmed D6: Bug Pending Handling action matrix. |
| 2026-07-08 | Confirmed D7: Bug Fixing action matrix. |
| 2026-07-08 | Confirmed D8: Bug Pending Verification action matrix. |
| 2026-07-08 | Confirmed D9: Bug Verified action matrix and close permission. |
| 2026-07-08 | Confirmed D10: Closed Bugs can be directly activated by reporter/tester, project owner, and system admin. |
| 2026-07-09 | Confirmed D10-1: default Bug close is blocked by any directly related unfinished task. |
| 2026-07-09 | Confirmed D10-2: Bug reactivation does not auto-reactivate or auto-create related tasks in the default template. |
| 2026-07-09 | Confirmed D10-3: Bug close/void does not auto-close related tasks by default; optional extension requires explicit prompt and audit. |
| 2026-07-09 | Confirmed D10-3 compatibility: auto-close mode overrides default task-blocking for eligible linked tasks and only blocks on non-eligible or failed linked handling. |
| 2026-07-08 | Confirmed D11: Bug current-handler rules distinguish repair handler from tester/verifier. |
| 2026-07-08 | Confirmed D11 extension: Bugs from test execution derive repair handler from related task/requirement, otherwise remain unassigned. |
| 2026-07-08 | Confirmed D11 extension: default verifier selection order for Pending Verification. |
| 2026-07-08 | Partially confirmed D12 and confirmed D13: workbench view naming, Created/Watched scope, manual watch, and comment mention behavior. |
| 2026-07-08 | Confirmed D13 extension: mentioned users automatically and continuously watch the item by default. |
| 2026-07-08 | Confirmed D12: workbench views and Created/Watched internal tabs. |
| 2026-07-08 | Confirmed D14: first-version Exception Center scope. |
| 2026-07-08 | Confirmed D15: workbench navigation order. |
| 2026-07-08 | Confirmed D16: task is a general execution object, may be created independently or by different roles, and should use multi-branch workflow design. |
| 2026-07-08 | Confirmed D17: task primary branches are requirement implementation, defect fix, test support, and standalone operation. |
| 2026-07-08 | Confirmed D18: task uses a shared state pool with Pending Assignment/In Processing/Pending Confirmation/Completed/Canceled; assigning a handler moves task from Pending Assignment to In Processing. |
| 2026-07-08 | Confirmed D19: default Pending Confirmation usage by task branch. |
| 2026-07-08 | Confirmed D20: Task Pending Assignment action matrix. |
| 2026-07-08 | Confirmed D21: Task In Processing action matrix. |
| 2026-07-08 | Confirmed D21-1: when to create Bug-linked tasks and the default manual creation strategy. |
| 2026-07-08 | Confirmed D22: linked task creation permission and default-handler rules. |
| 2026-07-08 | Confirmed D23: task confirmation-handler source, branch defaults, fallback, and audit rules. |
| 2026-07-08 | Confirmed D24: Task Pending Confirmation action matrix. |
| 2026-07-08 | Confirmed D24-1: task completion is blocked only by task-local conditions, not by upper-level object states. |
| 2026-07-08 | Confirmed D24-2: task cancellation is local by default and does not automatically propagate to related objects. |
| 2026-07-09 | Confirmed D24-3: task completion does not auto-drive related objects and does not produce extra completion prompts by default. |
| 2026-07-08 | Confirmed D25: requirement confirmation scope is limited to statuses and transitions. |
| 2026-07-08 | Confirmed D26: requirement uses Pending Assignment/In Processing/Pending Confirmation/Completed/Canceled, and a requirement with a handler is In Processing. |
| 2026-07-08 | Confirmed D27: requirement does not need Pending Confirmation by default and normally completes directly from In Processing. |
| 2026-07-08 | Confirmed default-template principle and D28: Requirement Pending Assignment action matrix. |
| 2026-07-08 | Confirmed D29: requirement cancel and reactivate rules. |
| 2026-07-08 | Confirmed D29-1: default requirement cancel is blocked by directly related active tasks or unclosed Bugs. |
| 2026-07-08 | Confirmed D30: Requirement In Processing action matrix. |
| 2026-07-08 | Confirmed D30-1: default requirement completion is blocked by any directly related unfinished task or unclosed Bug. |
| 2026-07-08 | Confirmed D30-2: completed requirements do not auto-reopen when related Bugs appear or reactivate; the issue goes to Exception Center instead. |
| 2026-07-08 | Confirmed D31: Requirement Canceled action matrix. |
| 2026-07-09 | Confirmed D32: iteration completion is blocked by any directly included unfinished requirement/task/Bug/test object. |
| 2026-07-09 | Confirmed D33: iteration cancellation uses the same direct-object strong gate as iteration completion in the default template. |
| 2026-07-09 | Confirmed D34: project closure is blocked by any directly scoped unfinished iteration/requirement/task/Bug/test object. |

## 9. Final Confirmation Summary

This section summarizes the confirmed baseline behavior for the default workflow templates and workbench model.

### 9.1 Core Architecture Summary

- The system is split into:
  - Workbench.
  - Workflow configuration.
  - Workflow execution.
- Workbench only displays items, filters, queues, and available actions.
- Workflow configuration defines statuses, transitions, permissions, handler routing, confirmation rules, and optional automation.
- Workflow execution is the authority for whether an action is available and what side effects happen.
- All rules confirmed in this PRD are **default workflow template rules**.
- Later, administrators may extend states and transitions, but extensions must preserve permission, audit, and action-derivation principles.

### 9.2 Workbench Summary

Main workbench entries:

1. Pending Handling / 待处理
2. Unassigned / 未分派
3. Exception Center / 异常中心
4. Created / Watched / 我发起/关注
5. Project Board / 项目看板

Workbench queue principles:

- `待处理`: current handler is the current user.
- `未分派`: current handler is empty.
- `我发起/关注`: explicit tracking scope only, not "everything I ever touched".

`我发起/关注` tabs:

- `我发起的`
- `我关注的`
- `提到我的`

Watch/mention rules:

- Users can manually watch supported objects.
- `@` is first implemented in comments.
- Typing `@` in comments should open a user selector.
- Mentioned users are automatically and continuously added to watch scope by default.

Exception Center first-version scope:

- Unassigned timeout
- Pending handling timeout
- Fixing timeout
- Pending verification timeout
- Verified not closed
- Verification failed
- Repeated activation
- High-priority unprocessed

### 9.3 Bug Default Template Summary

Bug status pool:

- Pending Handling
- Fixing
- Pending Verification
- Verified
- Closed

Key Bug principles:

- No separate `Assigned` status.
- Assignment is an action, not a status.
- Bug type selection determines target status through workflow configuration.
- Some actions may route by selected values, not by fixed buttons only.
- Users may be allowed to manually choose or override target status if the workflow action configuration allows it.

Bug type routing summary:

- Real defect types default to `Fixing`.
- Non-defect types default to `Pending Verification`.
- Reclassification after entering `Fixing` is supported.

Bug lifecycle summary:

- Create Bug
- Assign/claim if needed
- Confirm Bug type
- Enter `Fixing` or `Pending Verification`
- From `Fixing`, submit verification to `Pending Verification`
- Verification passed -> `Verified`
- Separate close action -> `Closed`
- Closed Bug may be reactivated

Bug current-handler summary:

- Repair handling and verification handling are separate concepts.
- Bugs from test execution do not default the repair handler to the test executor.
- Repair handler derivation for Bugs from test execution:
  1. Related task owner
  2. Related requirement owner
  3. Empty/unassigned
- Default verifier selection order is separately configured and defaults by source.

Bug close blocking summary:

- `Verified -> Closed` is blocked if any directly related task is not `Completed` or `Canceled`.
- This is a default-template hard block.

Bug reactivation linkage summary:

- Reactivating a Bug does not auto-reactivate related tasks.
- Reactivating a Bug does not auto-create new tasks.
- Follow-up execution handling is manual in the default template.

Bug close/void task auto-close summary:

- Default template: disabled.
- Optional extension: may be enabled by workflow template.
- If enabled, explicit prompt and audit are mandatory.

Bug key action summaries:

- Pending Handling:
  - claim
  - assign
  - confirm Bug type
  - transfer
  - add information
  - void/close
- Fixing:
  - submit verification
  - reclassify Bug type
  - transfer
  - assign/change handler
  - add information
  - void/close
- Pending Verification:
  - verification passed
  - verification failed
  - transfer verification
  - assign verifier
  - add information
  - void/close
- Verified:
  - close
  - return/reopen
  - view history
  - add information
- Closed:
  - activate
  - view history
  - add comment

### 9.4 Task Default Template Summary

Task primary branches:

- Requirement implementation
- Defect fix
- Test support
- Standalone operation

Task status pool:

- Pending Assignment
- In Processing
- Pending Confirmation
- Completed
- Canceled

Task state principles:

- No handler -> `Pending Assignment`
- Has handler -> `In Processing`
- `Pending Confirmation` is optional by branch/template
- Successful terminal state is `Completed`

Task branch default confirmation usage:

- Requirement implementation: no confirmation by default
- Defect fix: confirmation required by default
- Test support: confirmation required by default
- Standalone operation: configurable, default no confirmation

Linked task creation summary:

- Default handler of linked task = source object current handler
- Default creators of linked task:
  - source current handler
  - project owner
  - system admin
- If source object has no current handler, linked task enters `Pending Assignment`

Task confirmation-handler summary:

- `Submit Confirmation` switches current handler from execution handler to confirmation handler
- Confirmation-handler source is workflow-template configurable
- Final fallback confirmation handler = project owner

Task key action summaries:

- Pending Assignment:
  - claim
  - assign
  - edit
  - cancel
  - add information
- In Processing:
  - complete
  - submit confirmation
  - transfer
  - assign/change handler
  - add information
  - cancel
- Pending Confirmation:
  - approve/confirm passed
  - return for rework
  - transfer confirmation
  - assign/change confirmation handler
  - add information
  - cancel

### 9.5 Requirement Default Template Summary

Requirement confirmation scope in this round:

- Only statuses and transitions
- No business-scope, decomposition, or ownership-design expansion

Requirement status pool:

- Pending Assignment
- In Processing
- Pending Confirmation
- Completed
- Canceled

Requirement default path:

- Default:
  - `Pending Assignment -> In Processing -> Completed`
- Optional enhanced template:
  - `Pending Assignment -> In Processing -> Pending Confirmation -> Completed`

Requirement state principles:

- No current handler -> `Pending Assignment`
- Has current handler -> `In Processing`
- `Pending Confirmation` is not part of the default path
- `Canceled` is terminal but reactivatable

Requirement key action summaries:

- Pending Assignment:
  - claim
  - assign
  - edit
  - cancel
  - add information
- In Processing:
  - complete
  - optional submit confirmation
  - transfer
  - assign/change handler
  - add information
  - cancel
- Canceled:
  - reactivate
  - view history
  - add comment/add information

## 10. Remaining Open Items

The following areas are not yet fully confirmed in this PRD and should be addressed in the next round:

### 10.1 Object Areas Not Yet Confirmed

- Test case workflow
- Test execution / test sheet workflow
- Iteration workflow
- Project-level management workflow details

### 10.2 Cross-Cutting Details Still Worth Confirming

- Exact permission matrices by object and action
- Whether some object templates allow free claim vs assign-only
- Whether some default templates require mandatory cancel/reactivate reasons
- Whether some templates require mandatory attachments or result fields before completion
- Exact current-handler rules for requirement confirmation if an optional confirmation step is enabled

### 10.3 Implementation Translation Still Pending

- Backend workflow-template schema changes
- Backend workflow-execution API changes
- Workbench query/view model adjustments
- Comment mention input UI and backend parsing details
- Audit-log schema extensions for action-form routing and manual overrides
- Object-watch persistence and deduplication strategy

## 11. Iteration Workflow Confirmation

### D32. Iteration Completion Blocking Rules

Confirmed.

In the default workflow template, iteration completion is a strong gate and should be blocked by any directly included core object that is not closed out.

Default blocking rules for iteration completion:

- If any directly included requirement is not in `Completed` or `Canceled`, block iteration completion.
- If any directly included task is not in `Completed` or `Canceled`, block iteration completion.
- If any directly included Bug is not in `Closed`, block iteration completion.
- If any directly included test sheet/test execution object is not completed, block iteration completion.

Scope rules:

- The default template checks only objects directly included in the iteration.
- The default template does not recursively expand through requirement-task-Bug chains during iteration completion checks.
- Lower-level object closure logic should already be handled by each object's own workflow rules.

Rules:

- Blocking should happen during workflow execution when the user clicks iteration completion.
- The iteration status must remain unchanged when blocking happens.
- The response should clearly show why completion was blocked, including practical counts or lists of blocking objects where possible.
- Later workflow templates may refine this rule, but the default template should keep iteration completion strict and directly scoped.

### D33. Iteration Cancel Blocking Rules

Confirmed.

In the default workflow template, iteration cancellation should also be treated as a strong gate instead of a silent bulk stop action.

Default blocking rules for iteration cancellation:

- If any directly included requirement is not in `Completed` or `Canceled`, block iteration cancellation.
- If any directly included task is not in `Completed` or `Canceled`, block iteration cancellation.
- If any directly included Bug is not in `Closed`, block iteration cancellation.
- If any directly included test sheet/test execution object is not completed, block iteration cancellation.

Rules:

- The default template checks only objects directly included in the iteration.
- The default template does not automatically cancel included objects.
- Blocking should happen during workflow execution when the user clicks iteration cancellation.
- The iteration status must remain unchanged when blocking happens.
- The response should clearly show why cancellation was blocked.
- A later special workflow template or privileged management action may define a force-cancel path, but that should be treated as an explicit exception rather than baseline behavior.

## 12. Project Workflow Confirmation

### D34. Project Close Blocking Rules

Confirmed.

In the default workflow template, project closure is a top-level strong gate and should be blocked by any directly scoped project object that is not closed out.

Default blocking rules for project closure:

- If any project iteration is not in `Completed` or `Canceled`, block project closure.
- If any project requirement is not in `Completed` or `Canceled`, block project closure.
- If any project task is not in `Completed` or `Canceled`, block project closure.
- If any project Bug is not in `Closed`, block project closure.
- If any project test sheet/test execution object is not completed, block project closure.

Scope rules:

- The default template checks objects directly belonging to the project scope.
- The default template does not need to recursively expand through requirement-task-Bug chains during project closure checks.
- Lower-level object closure logic should already be handled by each object's own workflow rules.

Rules:

- Blocking should happen during workflow execution when the user clicks project closure.
- The project status must remain unchanged when blocking happens.
- The response should clearly show why closure was blocked, including practical counts or lists of blocking objects where possible.
- The default template does not automatically cancel or close all project objects.
- Later workflow templates may define exceptional force-close or guided cleanup paths, but the baseline default template should remain strict.
