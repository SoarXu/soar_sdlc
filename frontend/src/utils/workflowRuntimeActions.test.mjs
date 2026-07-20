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

function action(transitionId, overrides = {}) {
  return {
    transition_id: transitionId,
    action_name: `动作${transitionId}`,
    button_type: 'success',
    list_display: 'more',
    sort_order: 100,
    ui_config: {},
    ...overrides
  }
}

{
  const result = splitListActions([
    action(1, { button_type: 'danger', sort_order: 10 }),
    action(2, { sort_order: 20 })
  ])

  assert.deepEqual(result.primaryActions, [])
  assert.deepEqual(result.moreActions.map((item) => item.transition_id), [1, 2])
}

{
  const result = splitListActions([
    action(1, { button_type: 'danger', list_display: 'primary', sort_order: 20 }),
    action(2, { list_display: 'primary', sort_order: 10 }),
    action(3, { sort_order: 20 })
  ])

  assert.deepEqual(result.primaryActions.map((item) => item.transition_id), [2, 1])
  assert.deepEqual(result.moreActions.map((item) => item.transition_id), [3])
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

  assert.equal(actionNeedsDialog(action(3)), false)
}

{
  const result = visibleDetailActions([
    action(2, { sort_order: 20 }),
    action(1, { sort_order: 10 })
  ])

  assert.deepEqual(result.map((item) => item.transition_id), [1, 2])
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
            { object_type: 'project', id: 3, transitions: [{ transition_id: 31 }] },
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
  assert.deepEqual(result, { 3: [{ transition_id: 31 }], 8: [] })
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
