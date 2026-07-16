import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const componentPath = fileURLToPath(new URL('./WorkflowDesigner.vue', import.meta.url))
const source = await readFile(componentPath, 'utf8')

assert.match(source, /import WorkflowAdvancedConfigDrawer from '\.\/WorkflowAdvancedConfigDrawer\.vue'/)
assert.match(source, /applyAdvancedConfigDraft/)
assert.match(source, /configuredAdvancedSectionCount/)
assert.match(source, /<WorkflowAdvancedConfigDrawer[\s\S]*v-model="advancedDrawerVisible"[\s\S]*:transition="selectedTransition"[\s\S]*:states="states"[\s\S]*:role-options="roleOptions"[\s\S]*:target-types="targetTypes"[\s\S]*@apply="applyAdvancedDraft"/)
assert.match(source, /applyAdvancedConfigDraft\(selectedTransition\.value, draft\)/)
assert.match(source, /configuredAdvancedSectionCount\(selectedTransition, states\)/)
assert.match(source, /class="workflow-advanced-entry"/)
assert.match(source, />\s*高级配置\s*</)
assert.match(source, /:disabled="selectedUnsupportedSections\.length > 0"/)
assert.match(source, /高级配置已禁用/)

assert.doesNotMatch(source, /<el-collapse/)
for (const removedFunction of [
  'addConditionRoute',
  'removeConditionRoute',
  'addFormField',
  'removeFormField',
  'setValidator',
  'toggleAutomation'
]) {
  assert.doesNotMatch(source, new RegExp(`function ${removedFunction}\\b`))
}

assert.match(source, /async function confirmDiscardAdvancedDraft\(\)/)
assert.match(source, /advancedDrawer\.value\?\.hasPendingChanges\?\.\(\)/)
assert.match(source, /advancedDrawer\.value\.confirmDiscardPendingChanges\(\)/)
assert.match(source, /onBeforeRouteLeave\(async \(\) => confirmDiscardAdvancedDraft\(\)\)/)
assert.match(source, /window\.addEventListener\('beforeunload', onBeforeUnload\)/)
assert.match(source, /window\.removeEventListener\('beforeunload', onBeforeUnload\)/)

console.log('workflow designer drawer integration tests passed')
