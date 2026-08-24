import assert from 'node:assert/strict'

import { setWorkflowStateEnabled } from './workflowStateAvailability.js'

const states = [
  { id: 1, status_name: '开始', enabled: true },
  { id: 2, status_name: '处理中', enabled: true },
  { id: 3, status_name: '待确认', enabled: true }
]
const transitions = [
  { id: 11, action_name: '进入处理', from_state_id: 1, to_state_id: 2, enabled: true },
  { id: 12, action_name: '提交确认', from_state_id: 2, to_state_id: 3, enabled: true },
  { id: 13, action_name: '自环', from_state_id: 2, to_state_id: 2, enabled: true },
  {
    id: 14,
    action_name: '手工停用',
    from_state_id: 1,
    to_state_id: 2,
    enabled: false,
    auto_disabled_by_state: false
  },
  { id: 15, action_name: '无关流转', from_state_id: 1, to_state_id: 3, enabled: true }
]
const originalStates = structuredClone(states)
const originalTransitions = structuredClone(transitions)

const disabled = setWorkflowStateEnabled(states, transitions, 2, false)
assert.notStrictEqual(disabled.states, states)
assert.notStrictEqual(disabled.transitions, transitions)
assert.deepEqual(states, originalStates)
assert.deepEqual(transitions, originalTransitions)
assert.equal(disabled.states.find((item) => item.id === 2).enabled, false)
assert.equal(disabled.transitions.length, transitions.length)
for (const name of ['进入处理', '提交确认', '自环']) {
  const transition = disabled.transitions.find((item) => item.action_name === name)
  assert.equal(transition.enabled, false)
  assert.equal(transition.auto_disabled_by_state, true)
}
assert.deepEqual(
  disabled.transitions.find((item) => item.action_name === '手工停用'),
  transitions.find((item) => item.action_name === '手工停用')
)
assert.deepEqual(
  disabled.transitions.find((item) => item.action_name === '无关流转'),
  transitions.find((item) => item.action_name === '无关流转')
)

const bothDisabled = setWorkflowStateEnabled(disabled.states, disabled.transitions, 3, false)
const oneEndpointRestored = setWorkflowStateEnabled(bothDisabled.states, bothDisabled.transitions, 2, true)
const waitingTransition = oneEndpointRestored.transitions.find((item) => item.action_name === '提交确认')
assert.equal(waitingTransition.enabled, false)
assert.equal(waitingTransition.auto_disabled_by_state, true)

const restored = setWorkflowStateEnabled(
  oneEndpointRestored.states,
  oneEndpointRestored.transitions,
  3,
  true
)
for (const name of ['进入处理', '提交确认', '自环']) {
  const transition = restored.transitions.find((item) => item.action_name === name)
  assert.equal(transition.enabled, true)
  assert.equal(transition.auto_disabled_by_state, false)
}
const manuallyDisabled = restored.transitions.find((item) => item.action_name === '手工停用')
assert.equal(manuallyDisabled.enabled, false)
assert.equal(manuallyDisabled.auto_disabled_by_state, false)

console.log('workflow state availability tests passed')
