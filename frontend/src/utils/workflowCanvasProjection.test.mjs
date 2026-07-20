import assert from 'node:assert/strict'

import { projectWorkflowCanvas } from './workflowCanvasProjection.js'

const states = [
  { id: 1, status_name: 'Pending', enabled: true, sort_order: 10 },
  { id: 2, status_name: 'Processing', enabled: true, sort_order: 20 },
  { id: 3, status_name: 'Retired pending', enabled: false, sort_order: 30 }
]
const transitions = [
  { id: 11, from_state_id: 1, to_state_id: 2, action_name: 'Claim', sort_order: 10 },
  { id: 13, from_state_id: 1, to_state_id: 1, action_name: 'Add info', sort_order: 30 },
  { id: 12, from_state_id: 1, to_state_id: 1, action_name: 'Edit', sort_order: 20 },
  { id: 15, from_state_id: 3, to_state_id: 1, action_name: 'Retired route', sort_order: 35 },
  { id: 14, from_state_id: 99, to_state_id: 1, action_name: 'Invalid', sort_order: 40 }
]

{
  const statesSnapshot = structuredClone(states)
  const transitionsSnapshot = structuredClone(transitions)
  const result = projectWorkflowCanvas(states, transitions)

  assert.deepEqual(result.activeStates.map((item) => item.id), [1, 2])
  assert.deepEqual(result.inactiveStates.map((item) => item.id), [3])
  assert.deepEqual(result.routedTransitions.map((item) => item.id), [11])
  assert.deepEqual(result.stateActionsByStateId.get(1).map((item) => item.id), [12, 13])
  assert.deepEqual(result.stateActionsByStateId.get(2), [])
  assert.equal(result.stateActionsByStateId.has(99), false)
  assert.equal(result.routedTransitions[0], transitions[0])
  assert.equal(result.stateActionsByStateId.get(1)[0], transitions[2])
  assert.deepEqual(states, statesSnapshot)
  assert.deepEqual(transitions, transitionsSnapshot)
}

{
  const result = projectWorkflowCanvas(
    [{ id: 's', enabled: true }],
    [
      { id: '10', from_state_id: 's', to_state_id: 's', sort_order: 10 },
      { id: '2', from_state_id: 's', to_state_id: 's', sort_order: 10 },
      { id: 'a', from_state_id: 's', to_state_id: 's', sort_order: 'invalid' }
    ]
  )

  assert.deepEqual(result.stateActionsByStateId.get('s').map((item) => item.id), ['a', '2', '10'])
}

assert.deepEqual(projectWorkflowCanvas([], []), {
  activeStates: [],
  inactiveStates: [],
  routedTransitions: [],
  stateActionsByStateId: new Map()
})

console.log('workflow canvas projection tests passed')
