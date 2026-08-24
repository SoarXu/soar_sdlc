# Project Task Workflow Edit Command Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the project-detail task edit entry follow workflow visibility and grouping, and route the workflow edit command to the existing task editor.

**Architecture:** Keep `WorkflowActionButtons` as the source of workflow action visibility and grouping. Remove the project-detail task row's hardcoded edit button, then handle the component's existing `command` event in `ProjectDetailView` exactly as the requirement list and global task list already do.

**Tech Stack:** Vue 3, Element Plus, JavaScript source-contract tests, Node.js, Vite.

---

## Execution Rules

- Use @test-driven-development: change the focused contract test first, run it and verify the intended failure, then edit production code.
- Use @systematic-debugging if the focused test fails for an unrelated reason.
- Use @verification-before-completion before updating N-003 or claiming success.
- Work in the current workspace because the issue and design documents already exist here.
- Do not commit, push, merge, or create a PR until the repository-mandated delivery confirmation is answered.
- Preserve unrelated changes in `issue.md`, `deploy/`, `deploy.tar.gz`, N-001, and its plan documents.

### Task 1: Lock the task action contract with a failing test

**Files:**
- Modify: `frontend/src/views/projectDetailWorkflowIterationLayout.test.mjs:35-55`
- Read: `frontend/src/views/ProjectDetailView.vue:195-224`
- Read: `frontend/src/views/ProjectDetailView.vue:1315-1370`

**Step 1: Extract the task template in the existing contract test**

Add boundaries next to the existing requirement extraction:

```javascript
const tasksStart = source.indexOf('<template v-else-if="activeTab === \'tasks\'">')
const tasksEnd = source.indexOf('<template v-else-if="activeTab === \'testCases\'">', tasksStart)
assert.notEqual(tasksStart, -1)
assert.notEqual(tasksEnd, -1)
const tasksTemplate = source.slice(tasksStart, tasksEnd)
```

Use the actual next template marker from the source if its casing differs; do not broaden the slice to the whole component.

**Step 2: Add the desired task assertions**

Require all of the following:

```javascript
assert.doesNotMatch(
  tasksTemplate,
  /<el-button v-if="canEditWorkItem\(row\)" link type="primary" @click="openTaskEdit\(row\)">编辑<\/el-button>/,
  'task edit visibility must come from workflow configuration only'
)
assert.match(tasksTemplate, /<WorkflowActionButtons/)
assert.match(tasksTemplate, /@command="handleTaskWorkflowCommand\(row, \$event\)"/)
assert.match(tasksTemplate, /@confirm="removeTask\(row\.id\)"/)
assert.match(
  source,
  /function handleTaskWorkflowCommand\(row, \{ commandType \}\) \{\s*if \(commandType === 'edit'\) openTaskEdit\(row\)/
)
```

Keep the existing requirement assertions unchanged. Add an explicit Bug audit assertion that its current fixed edit entry remains present, documenting that Bug is outside this change until its workflow defines an edit command.

**Step 3: Run the test to verify RED**

Run:

```bash
cd frontend
node src/views/projectDetailWorkflowIterationLayout.test.mjs
```

Expected: FAIL because the task template still contains the fixed button and lacks `@command="handleTaskWorkflowCommand(row, $event)"`.

**Step 4: Confirm failure quality**

The first failure must describe the task edit contract. If the test fails on a missing slice boundary or malformed regular expression, correct the test and rerun until it fails only because production behavior is missing.

**Step 5: Git checkpoint**

Do not commit. Record the test file in the final delivery summary.

### Task 2: Route task editing through the workflow command

**Files:**
- Modify: `frontend/src/views/ProjectDetailView.vue:221-223`
- Modify: `frontend/src/views/ProjectDetailView.vue:1354-1367`
- Test: `frontend/src/views/projectDetailWorkflowIterationLayout.test.mjs`

**Step 1: Remove the fixed task edit button**

Restructure the task operation cell to use the same readable multi-line layout as requirements:

```vue
<template #default="{ row }">
  <WorkflowActionButtons
    object-type="task"
    :object-id="row.id"
    mode="list"
    :transitions="projectWorkflowTransitionsFor('task', row.id)"
    :auto-load="false"
    :users="users"
    @command="handleTaskWorkflowCommand(row, $event)"
    @executed="refreshAfterMutation"
  />
  <el-popconfirm
    v-if="canDeleteCurrentWorkItem && !projectClosed"
    title="确认删除该任务？"
    @confirm="removeTask(row.id)"
  >
    <template #reference><el-button link type="danger">删除</el-button></template>
  </el-popconfirm>
</template>
```

Do not change the workflow transition data, delete permission, or operation-column width in this task.

**Step 2: Add the task command handler**

Place the handler beside `openTaskEdit`:

```javascript
function handleTaskWorkflowCommand(row, { commandType }) {
  if (commandType === 'edit') openTaskEdit(row)
}
```

Do not call `executeWorkflowTransition`; edit is a local navigation/form command and must not create a status-operation record.

**Step 3: Run the focused test to verify GREEN**

Run:

```bash
cd frontend
node src/views/projectDetailWorkflowIterationLayout.test.mjs
```

Expected: `project detail workflow and iteration layout contract passed`.

**Step 4: Run adjacent command tests**

Run:

```bash
cd frontend
node src/utils/workflowRuntimeActions.test.mjs
node src/views/workbenchWorkflowCommands.test.mjs
```

Expected: both commands pass, proving the shared command classification and other surfaces remain intact.

**Step 5: Git checkpoint**

Do not commit. Record `ProjectDetailView.vue` and the focused test in the final delivery summary.

### Task 3: Execute the approved validation plan

**Files:**
- Read: `docs/plans/2026-08-22-project-task-workflow-edit-command-validation.md`
- Modify after evidence: `docs/issues/2026-08-22-后续问题清单.md`

**Step 1: Run all automated checks in the validation plan**

Execute the focused tests, frontend full test suite, production build, and whitespace checks exactly as listed in the validation document.

**Step 2: Perform browser acceptance**

Verify task edit in the three workflow configurations: primary, more, and absent. Confirm the edit dialog opens with the selected row and that no workflow transition request is sent for the edit command.

**Step 3: Audit the Bug entry without changing it**

Confirm the default Bug workflow does not return an edit command and that the existing fixed Bug edit button remains functional. Record this as an explicit non-regression result, not as completion of Bug workflow migration.

**Step 4: Update N-003 with exact evidence**

If every required check passes, change N-003 from `待实施` to `待验证` and replace `尚未实施` with exact commands, counts, build output, and browser scenarios. Do not mark it `已解决` before product acceptance.

**Step 5: Request delivery confirmation**

Report the implementation and fresh verification evidence, then ask the required five-option Git delivery question. Perform no Git operation until the user chooses.
