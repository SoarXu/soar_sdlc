import assert from 'node:assert/strict'

import { requestWorkflowOrganization } from './workflowLayoutInteraction.js'

function workflowFixture() {
  return {
    states: [
      { id: 1, status_name: '待处理', x: 480, y: 300 },
      { id: 2, status_name: '处理中', x: 160, y: 120 }
    ],
    transitions: [
      { id: 11, from_state_id: 1, to_state_id: 2 },
      { id: 12, from_state_id: 2, to_state_id: 1 }
    ]
  }
}

{
  const { states, transitions } = workflowFixture()
  const originalStates = structuredClone(states)
  const originalTransitions = structuredClone(transitions)

  const result = await requestWorkflowOrganization({
    states,
    transitions,
    initialStateId: 2,
    confirm: async () => { throw 'cancel' },
    notifyEmpty: () => assert.fail('non-empty workflow must not notify')
  })

  assert.equal(result.organized, false)
  assert.strictEqual(result.states, states)
  assert.deepEqual(states, originalStates)
  assert.deepEqual(transitions, originalTransitions)
}

{
  const { states, transitions } = workflowFixture()
  const originalStates = structuredClone(states)

  const result = await requestWorkflowOrganization({
    states,
    transitions,
    initialStateId: 2,
    confirm: async () => { throw 'close' },
    notifyEmpty: () => assert.fail('non-empty workflow must not notify')
  })

  assert.equal(result.organized, false)
  assert.strictEqual(result.states, states)
  assert.deepEqual(states, originalStates)
}

{
  const { states, transitions } = workflowFixture()
  const confirmationError = new Error('message box failed')

  await assert.rejects(
    requestWorkflowOrganization({
      states,
      transitions,
      initialStateId: 2,
      confirm: async () => { throw confirmationError },
      notifyEmpty: () => assert.fail('non-empty workflow must not notify')
    }),
    (error) => error === confirmationError
  )
}

{
  const { states, transitions } = workflowFixture()
  const originalStates = structuredClone(states)
  const originalTransitions = structuredClone(transitions)
  let confirmCount = 0

  const result = await requestWorkflowOrganization({
    states,
    transitions,
    initialStateId: 2,
    confirm: async () => { confirmCount += 1 },
    notifyEmpty: () => assert.fail('non-empty workflow must not notify')
  })

  assert.equal(confirmCount, 1)
  assert.equal(result.organized, true)
  assert.notStrictEqual(result.states, states)
  assert.notDeepEqual(result.states, originalStates)
  assert.deepEqual(states, originalStates)
  assert.deepEqual(transitions, originalTransitions)
}

{
  const states = []
  const transitions = []
  let confirmCount = 0
  let notifyCount = 0

  const result = await requestWorkflowOrganization({
    states,
    transitions,
    initialStateId: null,
    confirm: async () => { confirmCount += 1 },
    notifyEmpty: () => { notifyCount += 1 }
  })

  assert.equal(confirmCount, 0)
  assert.equal(notifyCount, 1)
  assert.equal(result.organized, false)
  assert.strictEqual(result.states, states)
}

{
  const { states, transitions } = workflowFixture()
  const result = await requestWorkflowOrganization({
    states,
    transitions,
    initialStateId: 2,
    confirm: async () => {},
    notifyEmpty: () => {}
  })
  const initialState = result.states.find((state) => state.id === 2)
  const otherState = result.states.find((state) => state.id === 1)

  assert.ok(initialState.x < otherState.x, 'the configured initial state must occupy the first layer')
}

console.log('workflow layout interaction tests passed')
