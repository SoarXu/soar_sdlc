import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const files = [
  'RequirementsView.vue',
  'TasksView.vue',
  'BugsView.vue',
  'RequirementDetailView.vue',
  'TaskDetailView.vue',
  'BugDetailView.vue',
  'IterationDetailView.vue',
  'ProjectDetailView.vue'
]

for (const file of files) {
  const source = readFileSync(`frontend/src/views/${file}`, 'utf8')
  assert.match(source, /status_name/)
}

const workbench = readFileSync('frontend/src/utils/workbenchViewModel.js', 'utf8')
assert.doesNotMatch(workbench, /STATUS_LABELS|pending_assignment:\s*'|in_processing:\s*'|pending_handling:\s*'|fixing:\s*'/)
assert.match(workbench, /item\.status_name/)
assert.match(workbench, /item\.state_category === 'terminal'/)

console.log('workflow status display source contract passed')
