import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const programsView = await readFile(new URL('./ProgramsView.vue', import.meta.url), 'utf8')
const projectsView = await readFile(new URL('./ProjectsView.vue', import.meta.url), 'utf8')
const workflowActionButtons = await readFile(new URL('../components/WorkflowActionButtons.vue', import.meta.url), 'utf8')

function templateBlock(source, marker, nextMarker) {
  const start = source.indexOf(marker)
  const end = source.indexOf(nextMarker, start)
  assert.notEqual(start, -1, `missing template marker: ${marker}`)
  assert.notEqual(end, -1, `missing template boundary: ${nextMarker}`)
  return source.slice(start, end)
}

function assertBefore(source, first, second, message) {
  const firstIndex = source.indexOf(first)
  const secondIndex = source.indexOf(second)
  assert.notEqual(firstIndex, -1, `${message}: missing marker ${first}`)
  assert.notEqual(secondIndex, -1, `${message}: missing marker ${second}`)
  assert.ok(firstIndex < secondIndex, message)
}

const programActions = templateBlock(
  programsView,
  "<template v-if=\"row.nodeType === 'program'\">",
  '<template v-else>'
)

for (const action of ['start', 'suspend', 'close', 'activate']) {
  assertBefore(
    programActions,
    `openStatusDialog(row, 'program', '${action}')`,
    'openEdit(row)',
    `project-group ${action} action must render before Edit`
  )
}

const projectActions = templateBlock(
  programsView,
  '<template v-else>',
  '</el-table-column>'
)

assertBefore(
  projectActions,
  '<WorkflowActionButtons',
  'openProjectEdit(row.id)',
  'project workflow actions must render before Edit in the project-group tree'
)

assertBefore(
  workflowActionButtons,
  'workflow-primary-actions',
  '<slot name="after-primary" />',
  'workflow action buttons must render primary lifecycle actions before after-primary content'
)

const projectListWorkflowActions = templateBlock(
  projectsView,
  '<WorkflowActionButtons',
  '</WorkflowActionButtons>'
)
const projectListAfterPrimaryActions = templateBlock(
  projectListWorkflowActions,
  '<template #after-primary>',
  '</template>'
)

assert.ok(
  projectListAfterPrimaryActions.includes('openEdit(row)'),
  'project list must place Edit in WorkflowActionButtons after-primary content'
)
