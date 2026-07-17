import assert from 'node:assert/strict'

import * as workflowRuntimeActions from './workflowRuntimeActions.js'
import {
  actionNeedsDialog,
  actionNeedsTargetStateSelection,
  workflowCommandType,
  splitListActions,
  visibleDetailActions
} from './workflowRuntimeActions.js'

const { replaceWorkflowTransitionMap } = workflowRuntimeActions

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
    allowed_target_states: [{ id: 2, status_name: '修复中' }, { id: 3, status_name: '待验证' }]
  })), true)

  assert.equal(actionNeedsTargetStateSelection(action('reroute', {
    routing_mode: 'manual_allowed',
    allowed_target_states: [{ id: 4, status_name: '已完成' }]
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

{
  assert.equal(typeof replaceWorkflowTransitionMap, 'function')
  const replacements = []
  let requestedItems = []
  const result = await replaceWorkflowTransitionMap(
    async (items) => {
      requestedItems = items
      assert.deepEqual(replacements, [{}])
      return {
        data: {
          items: [
            { object_type: 'project', id: 3, transitions: [{ action_key: 'start' }] },
            { object_type: 'project', id: 8, transitions: null }
          ]
        }
      }
    },
    [3, 3, 8],
    (value) => replacements.push(value)
  )

  assert.deepEqual(requestedItems, [
    { object_type: 'project', id: 3 },
    { object_type: 'project', id: 8 }
  ])
  assert.deepEqual(result, { 3: [{ action_key: 'start' }], 8: [] })
  assert.deepEqual(replacements, [{}, result])
}

{
  const replacements = []
  await assert.rejects(
    replaceWorkflowTransitionMap(
      async () => { throw new Error('transition service unavailable') },
      [5, 5],
      (value) => replacements.push(value)
    ),
    /transition service unavailable/
  )
  assert.deepEqual(replacements, [{}, {}])
}

console.log('workflowRuntimeActions tests passed')
