import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./DashboardView.vue', import.meta.url), 'utf8')

assert.match(source, /@command="handleWorkflowCommand\(row, \$event\)"/)
assert.match(source, /import RequirementEditDialog/)
assert.match(source, /import TaskEditDialog/)
assert.match(source, /import BugEditDialog/)
assert.match(source, /resolveWorkbenchWorkflowCommand/)
assert.match(source, /async function handleEditorSaved/)
assert.match(source, /await loadWorkbench\(\)/)

console.log('workbench workflow command integration tests passed')
