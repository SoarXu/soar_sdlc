import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const viewPath = fileURLToPath(new URL('./ProjectsView.vue', import.meta.url))
const source = await readFile(viewPath, 'utf8')

assert.match(
  source,
  /const defaultWorkflowScheme = computed\(\(\) => \(\s*enabledWorkflowSchemes\.value\.find\(\(scheme\) => scheme\.name === DEFAULT_WORKFLOW_SCHEME_NAME\)/
)

const resetFormStart = source.indexOf('function resetForm()')
const buildProjectTreeStart = source.indexOf('function buildProjectTree(', resetFormStart)
assert.notEqual(resetFormStart, -1)
assert.notEqual(buildProjectTreeStart, -1)
const resetFormBody = source.slice(resetFormStart, buildProjectTreeStart)
assert.match(resetFormBody, /assignee_rule_config_id: defaultWorkflowScheme\.value\?\.id \?\? null/)

const selectorStart = source.indexOf('<el-select v-model="form.assignee_rule_config_id"')
const selectorEnd = source.indexOf('>', selectorStart)
assert.notEqual(selectorStart, -1)
assert.notEqual(selectorEnd, -1)
assert.doesNotMatch(source.slice(selectorStart, selectorEnd + 1), /\bclearable\b/)

console.log('project default workflow scheme source contract passed')
