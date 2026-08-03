import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const designer = await readFile(new URL('./WorkflowDesigner.vue', import.meta.url), 'utf8')
const workflowView = await readFile(new URL('../views/WorkflowView.vue', import.meta.url), 'utf8')

assert.match(
  designer,
  /\{ label: '项目', value: 'project' \}/,
  'workflow scheme designer must expose the project lifecycle flow'
)
assert.match(
  workflowView,
  /项目、需求、任务、Bug 的可视化工作流/,
  'workflow scheme descriptions must state that project flows are configurable'
)

console.log('workflow designer project type contract passed')
