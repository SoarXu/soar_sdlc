import assert from 'node:assert/strict'

import { stateRoleOptions } from './workflowStateRoles.js'

for (const objectType of ['requirement', 'task', 'bug']) {
  assert.deepEqual(
    stateRoleOptions(objectType).map((option) => option.value),
    ['unassigned', 'waiting_iteration', 'active_work']
  )
}

for (const objectType of ['project', 'iteration', 'program']) {
  assert.deepEqual(stateRoleOptions(objectType), [])
}

console.log('workflow state roles tests passed')
