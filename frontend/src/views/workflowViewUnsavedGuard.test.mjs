import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const viewPath = fileURLToPath(new URL('./WorkflowView.vue', import.meta.url))
const designerPath = fileURLToPath(new URL('../components/WorkflowDesigner.vue', import.meta.url))
const [viewSource, designerSource] = await Promise.all([
  readFile(viewPath, 'utf8'),
  readFile(designerPath, 'utf8')
])

assert.match(viewSource, /<WorkflowDesigner[\s\S]*ref="workflowDesigner"/)
assert.match(viewSource, /const workflowDesigner = ref\(null\)/)
assert.match(
  designerSource,
  /defineExpose\(\{[\s\S]*confirmDiscardWorkflowChanges[\s\S]*\}\)/
)

const backToListStart = viewSource.indexOf('async function backToList()')
const backToListEnd = viewSource.indexOf('async function loadData()', backToListStart)
assert.notEqual(backToListStart, -1)
assert.notEqual(backToListEnd, -1)
const backToListDeclaration = viewSource.slice(backToListStart, backToListEnd)

function createBackToList(workflowDesigner, viewMode, resetForm) {
  return Function(
    'workflowDesigner',
    'viewMode',
    'resetForm',
    `${backToListDeclaration}; return backToList`
  )(workflowDesigner, viewMode, resetForm)
}

for (const scenario of [
  { confirmation: false, expectedView: 'detail', expectedResets: 0 },
  { confirmation: true, expectedView: 'list', expectedResets: 1 }
]) {
  let confirmations = 0
  let resets = 0
  const workflowDesigner = {
    value: {
      async confirmDiscardWorkflowChanges() {
        confirmations += 1
        return scenario.confirmation
      }
    }
  }
  const viewMode = { value: 'detail' }
  const backToList = createBackToList(workflowDesigner, viewMode, () => { resets += 1 })

  await backToList()

  assert.equal(confirmations, 1)
  assert.equal(resets, scenario.expectedResets)
  assert.equal(viewMode.value, scenario.expectedView)
}

let resetsWithoutDesigner = 0
const viewModeWithoutDesigner = { value: 'detail' }
const backToListWithoutDesigner = createBackToList(
  { value: null },
  viewModeWithoutDesigner,
  () => { resetsWithoutDesigner += 1 }
)
await backToListWithoutDesigner()
assert.equal(resetsWithoutDesigner, 1)
assert.equal(viewModeWithoutDesigner.value, 'list')

console.log('workflow view unsaved guard source contract passed')
