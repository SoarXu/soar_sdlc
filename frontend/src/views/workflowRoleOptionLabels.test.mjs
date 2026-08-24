import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const [workflowSource, projectSource] = await Promise.all([
  readFile(new URL('./WorkflowView.vue', import.meta.url), 'utf8'),
  readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8')
])

assert.match(workflowSource, /:role-options="workflowExecutionRoleOptions"/)
assert.match(workflowSource, /roleCatalog\.value[\s\S]*?role\.role_name[\s\S]*?role\.id/)
assert.match(projectSource, /const projectMemberRoleOptions = computed\(\(\) => \{[\s\S]*?roleCatalog\.value[\s\S]*?role\.role_name[\s\S]*?role\.id/)
assert.doesNotMatch(workflowSource, /development_lead|tech_lead/)
assert.doesNotMatch(projectSource, /development_lead|tech_lead/)

console.log('workflow role option labels passed')
