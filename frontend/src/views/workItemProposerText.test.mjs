import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { formatAuditValue } from '../utils/auditHistoryLabels.js'


function source(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8')
}


const requirementSources = [
  source('./RequirementsView.vue'),
  source('./ProjectDetailView.vue'),
  source('./IterationDetailView.vue'),
  source('./RequirementDetailView.vue'),
  source('../components/work-items/RequirementEditDialog.vue')
]
const bugSources = [
  source('./BugsView.vue'),
  source('./ProjectDetailView.vue'),
  source('./BugDetailView.vue'),
  source('../components/work-items/BugEditDialog.vue')
]
const allSources = [...new Set([...requirementSources, ...bugSources])]

for (const formSource of allSources) {
  assert.doesNotMatch(formSource, /proposer_id|reporter_id/)
  assert.match(formSource, /label="提出人"[\s\S]{0,120}<el-input[^>]+v-model="[^\"]+\.proposer"/)
}

assert.match(requirementSources[3], /\{\{ requirement\.proposer \|\| '-' \}\}/)
assert.match(bugSources[2], /\{\{ bug\.proposer \|\| '-' \}\}/)
assert.equal(formatAuditValue('proposer', '外部客户 张三', { users: [] }), '外部客户 张三')

for (const taskSource of [
  source('./TasksView.vue'),
  source('./TaskDetailView.vue'),
  source('../components/work-items/TaskEditDialog.vue')
]) {
  assert.doesNotMatch(taskSource, /label="提出人"/)
}

const workflowDesigner = source('../components/WorkflowDesigner.vue')
assert.doesNotMatch(workflowDesigner, /value: '(?:proposer|reporter|bug_reporter)'/)

console.log('work item proposer text contracts passed')
