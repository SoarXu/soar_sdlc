import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const designer = readFileSync('frontend/src/components/WorkflowDesigner.vue', 'utf8')
const drawer = readFileSync('frontend/src/components/WorkflowAdvancedConfigDrawer.vue', 'utf8')

for (const legacyField of ['status_key', 'from_status', 'to_status']) {
  assert.doesNotMatch(designer, new RegExp(legacyField))
}
assert.doesNotMatch(drawer, /status_key|from_status|to_status/)
assert.match(designer, /initial_state_id/)
assert.match(designer, /from_state_id/)
assert.match(designer, /to_state_id/)
assert.match(designer, /nextTemporaryStateId/)
assert.match(designer, /Math\.min\(-1/)

console.log('workflow state identity source contract passed')
