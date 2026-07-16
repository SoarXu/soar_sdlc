import assert from 'node:assert/strict'

import {
  actionNeedsDialog,
  actionNeedsTargetStatusSelection,
  workflowCommandType,
  splitListActions,
  visibleDetailActions
} from './workflowRuntimeActions.js'

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

{
  assert.equal(actionNeedsDialog(action('confirm_bug_type', {
    routing_mode: 'automatic_with_override',
    allowed_target_statuses: ['fixing', 'pending_verification']
  })), true)

  assert.equal(actionNeedsTargetStatusSelection(action('reroute', {
    routing_mode: 'manual_allowed',
    allowed_target_statuses: ['completed']
  })), true)

  assert.equal(actionNeedsDialog(action('claim')), false)
}

{
  const result = visibleDetailActions([
    action('hidden_in_detail', { ui_config: { visible_in_detail: false } }),
    action('visible', { list_priority: 1 })
  ])

  assert.deepEqual(result.map((item) => item.action_key), ['visible'])
}

{
  assert.equal(workflowCommandType(action('edit', { ui_config: { command_type: 'edit' } })), 'edit')
  assert.equal(workflowCommandType(action('complete')), '')
}

console.log('workflowRuntimeActions tests passed')
