import assert from 'node:assert/strict'

import {
  parseProjectDetailRouteState,
  serializeProjectDetailRouteState,
  projectDetailRouteQuery
} from './projectDetailRouteState.js'

const listKeys = ['requirements', 'tasks', 'testCases', 'testRuns', 'bugs']
const defaultList = { keyword: '', iteration_id: null, unfinished_work_items: false, page: 1, pageSize: 10 }
const defaultState = {
  testTab: 'cases',
  ...Object.fromEntries(listKeys.map((key) => [key, { ...defaultList }]))
}

assert.deepEqual(parseProjectDetailRouteState({}), defaultState)

{
  const state = {
    testTab: 'runs',
    requirements: { ...defaultList, keyword: '登录', iteration_id: 12, unfinished_work_items: true, page: 3, pageSize: 20 },
    tasks: { ...defaultList, keyword: '接口', iteration_id: 7, page: 2, pageSize: 50 },
    testCases: { ...defaultList, keyword: '回归', page: 4, pageSize: 10 },
    testRuns: { ...defaultList, keyword: 'v1', pageSize: 20 },
    bugs: { ...defaultList, keyword: '崩溃', iteration_id: 9, unfinished_work_items: true, page: 5, pageSize: 100 }
  }
  const query = serializeProjectDetailRouteState(state)
  assert.deepEqual(query, {
    test_tab: 'runs',
    requirements_keyword: '登录', requirements_iteration_id: '12', requirements_unfinished_work_items: '1', requirements_page: '3', requirements_page_size: '20',
    tasks_keyword: '接口', tasks_iteration_id: '7', tasks_page: '2', tasks_page_size: '50',
    testCases_keyword: '回归', testCases_page: '4',
    testRuns_keyword: 'v1', testRuns_page_size: '20',
    bugs_keyword: '崩溃', bugs_iteration_id: '9', bugs_unfinished_work_items: '1', bugs_page: '5', bugs_page_size: '100'
  })
  assert.deepEqual(parseProjectDetailRouteState(query), state)
  assert.deepEqual(projectDetailRouteQuery(state), query)
}

assert.deepEqual(parseProjectDetailRouteState({
  test_tab: 'invalid',
  requirements_keyword: [' first '], requirements_iteration_id: '4', requirements_page: '0', requirements_page_size: 'bad',
  tasks_iteration_id: '-2', tasks_page: '2.5',
  bugs_keyword: null
}), {
  ...defaultState,
  requirements: { ...defaultList, keyword: ' first ', iteration_id: 4 },
  tasks: { ...defaultList }
})

assert.deepEqual(serializeProjectDetailRouteState(defaultState), {})

console.log('projectDetailRouteState tests passed')
