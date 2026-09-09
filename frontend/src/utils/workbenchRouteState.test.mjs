import assert from 'node:assert/strict'

import {
  parseWorkbenchRouteState,
  serializeWorkbenchRouteState,
  workbenchRouteQuery
} from './workbenchRouteState.js'

const defaultState = {
  keyword: '',
  projectIds: [],
  iterationIds: [],
  types: [],
  stateIds: [],
  priorities: [],
  handlerIds: [],
  page: 1,
  pageSize: 20
}

assert.deepEqual(parseWorkbenchRouteState({}), defaultState)

{
  const state = {
    keyword: 'login failure',
    projectIds: [12, 7],
    iterationIds: [31, 32],
    types: ['requirement', 'bug'],
    stateIds: [4, 9],
    priorities: ['1', '3'],
    handlerIds: [18, 21],
    page: 3,
    pageSize: 50
  }
  const query = serializeWorkbenchRouteState(state)

  assert.deepEqual(query, {
    keyword: 'login failure',
    project_ids: '12,7',
    iteration_ids: '31,32',
    object_types: 'requirement,bug',
    state_ids: '4,9',
    priorities: '1,3',
    handler_ids: '18,21',
    page: '3',
    page_size: '50'
  })
  assert.deepEqual(parseWorkbenchRouteState(query), state)
  assert.deepEqual(workbenchRouteQuery(state), query)
}

assert.deepEqual(parseWorkbenchRouteState({
  project_ids: ['12', '7,8', '', null],
  object_types: ['task', 'bug']
}), {
  ...defaultState,
  projectIds: [12, 7, 8],
  types: ['task', 'bug']
})

assert.deepEqual(parseWorkbenchRouteState({
  iteration_ids: '31,32',
  state_ids: ['4', '9'],
  handler_ids: '18',
  object_types: 'bug',
  priorities: '1'
}), {
  ...defaultState,
  iterationIds: [31, 32],
  stateIds: [4, 9],
  handlerIds: [18],
  types: ['bug'],
  priorities: ['1']
})

for (const page of ['0', '-2', '1.5', 'not-a-number', '', null, undefined]) {
  assert.equal(parseWorkbenchRouteState({ page }).page, 1)
}

for (const pageSize of ['0', '-20', '2.5', 'not-a-number', '', null, undefined]) {
  assert.equal(parseWorkbenchRouteState({ page_size: pageSize }).pageSize, 20)
}

assert.deepEqual(serializeWorkbenchRouteState(defaultState), {})
assert.deepEqual(serializeWorkbenchRouteState({
  ...defaultState,
  projectIds: ['', null, undefined],
  types: []
}), {})

console.log('workbenchRouteState tests passed')
