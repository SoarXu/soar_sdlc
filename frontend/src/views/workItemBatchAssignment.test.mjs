import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const viewFiles = ['RequirementsView.vue', 'TasksView.vue', 'BugsView.vue']
for (const fileName of viewFiles) {
  const source = await readFile(new URL(`./${fileName}`, import.meta.url), 'utf8')
  assert.match(source, /type="selection"/)
  assert.match(source, /@selection-change=/)
  assert.match(source, /BatchAssignmentBar/)
  assert.match(source, /canSelectForBatchAssignment/)
  assert.match(source, /clearSelection/)
}

const testsView = await readFile(new URL('./TestsView.vue', import.meta.url), 'utf8')
assert.doesNotMatch(testsView, /BatchAssignmentBar/)

const projectDetailView = await readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8')
assert.equal((projectDetailView.match(/type="selection" width="48" :selectable="\(row\) => canSelectProjectWorkItemForBatchAssignment/g) || []).length, 3)
assert.equal((projectDetailView.match(/<BatchAssignmentBar/g) || []).length, 3)
for (const objectType of ['requirement', 'task', 'bug']) {
  assert.match(projectDetailView, new RegExp(`object-type="${objectType}"`))
}
assert.match(projectDetailView, /canSelectForBatchAssignment/)
assert.match(projectDetailView, /clearProjectWorkItemSelection/)

const dashboardView = await readFile(new URL('./DashboardView.vue', import.meta.url), 'utf8')
assert.equal((dashboardView.match(/type="selection"/g) || []).length, 1)
assert.match(dashboardView, /@selection-change="onWorkbenchSelectionChange"/)
assert.match(dashboardView, /<BatchAssignmentBar/)
assert.match(dashboardView, /canSelectWorkbenchItemForBatchAssignment/)
assert.match(dashboardView, /clearWorkbenchSelection/)

console.log('work item batch assignment view tests passed')
