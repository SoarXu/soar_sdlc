import assert from 'node:assert/strict'

import {
  groupStateTransitions,
  moveStateTransition,
  nextGroupSortOrder
} from './workflowTransitionOrdering.js'

function transition(id, group, order, overrides = {}) {
  return {
    id,
    action_name: `流转${id}`,
    from_state_id: 7,
    enabled: true,
    sort_order: order,
    ui_config: { list_display: group },
    ...overrides
  }
}

{
  const grouped = groupStateTransitions([
    transition(1, 'primary', 20),
    transition(2, 'primary', 10),
    transition(3, 'more', 10),
    transition(4, 'primary', 5, { enabled: false }),
    transition(5, 'primary', 5, { from_state_id: 8 })
  ], 7)

  assert.deepEqual(grouped.primary.map((item) => item.id), [2, 1])
  assert.deepEqual(grouped.more.map((item) => item.id), [3])
}

{
  const moved = moveStateTransition([
    transition(1, 'primary', 10),
    transition(2, 'primary', 20),
    transition(3, 'more', 10)
  ], 2, 'more', 0)
  const grouped = groupStateTransitions(moved, 7)

  assert.deepEqual(grouped.primary.map((item) => [item.id, item.sort_order]), [[1, 10]])
  assert.deepEqual(grouped.more.map((item) => [item.id, item.sort_order]), [[2, 10], [3, 20]])
  assert.equal(grouped.more[0].ui_config.list_display, 'more')
}

{
  assert.equal(nextGroupSortOrder([
    transition(1, 'more', 10),
    transition(2, 'more', 30),
    transition(3, 'primary', 90)
  ], 7, 'more'), 40)
}

console.log('workflow transition ordering tests passed')
