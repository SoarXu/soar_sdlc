import assert from 'node:assert/strict'

import { toWorkItemPatchPayload } from './workItemPatchPayload.js'


const source = {
  title: 'Editable title',
  owner_id: 42,
  status: 'completed',
  description: 'Editable description'
}
const payload = toWorkItemPatchPayload(source)

assert.deepEqual(payload, {
  title: 'Editable title',
  description: 'Editable description'
})
assert.equal(source.owner_id, 42)
assert.equal(source.status, 'completed')

console.log('workItemPatchPayload tests passed')
