import assert from 'node:assert/strict'

import { splitListActions } from './workflowRuntimeActions.js'

function action(actionKey, overrides = {}) {
  return {
    action_key: actionKey,
    action_name: actionKey,
    button_type: 'success',
    list_display: 'more',
    list_priority: 100,
    ui_config: {},
    ...overrides
  }
}

{
  const result = splitListActions([
    action('close', { button_type: 'danger', list_priority: 10 }),
    action('submit_validation', { list_priority: 20 })
  ])

  assert.equal(result.primaryAction.action_key, 'submit_validation')
  assert.deepEqual(result.moreActions.map((item) => item.action_key), ['close'])
}

{
  const result = splitListActions([
    action('close', { button_type: 'danger', list_display: 'primary', list_priority: 5 }),
    action('submit_validation', { list_display: 'primary', list_priority: 10 }),
    action('defer', { list_priority: 20 })
  ])

  assert.equal(result.primaryAction.action_key, 'close')
  assert.deepEqual(result.moreActions.map((item) => item.action_key), ['submit_validation', 'defer'])
}

{
  const result = splitListActions([
    action('hidden', { list_display: 'hidden', list_priority: 1 }),
    action('primary', { list_display: 'primary', list_priority: 2 }),
    action('more', { list_display: 'more', list_priority: 3 })
  ])

  assert.equal(result.primaryAction.action_key, 'primary')
  assert.deepEqual(result.moreActions.map((item) => item.action_key), ['more'])
}

console.log('workflowRuntimeActions tests passed')
