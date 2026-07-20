import assert from 'node:assert/strict'
import {
  WORKFLOW_LAYOUT,
  layoutWorkflowNodes
} from './workflowAutoLayout.js'

const state = (id, sortOrder = 0, extra = {}) => ({
  id,
  name: `State ${id}`,
  sort_order: sortOrder,
  x: -1,
  y: -1,
  ...extra
})

const transition = (from, to) => ({ from_state_id: from, to_state_id: to })
const byId = (items, id) => items.find((item) => item.id === id)

assert.deepEqual(WORKFLOW_LAYOUT, {
  marginX: 80,
  marginY: 80,
  layerGap: 240,
  rowGap: 120
})
assert.equal(Object.isFrozen(WORKFLOW_LAYOUT), true)

{
  const result = layoutWorkflowNodes(
    [state(1), state(2), state(3)],
    [transition(1, 2), transition(2, 3)],
    1
  )

  assert.deepEqual(result.map(({ id, x, y }) => ({ id, x, y })), [
    { id: 1, x: 80, y: 80 },
    { id: 2, x: 320, y: 80 },
    { id: 3, x: 560, y: 80 }
  ])
}

{
  const result = layoutWorkflowNodes(
    [state(4, 40), state(2, 20), state(1, 10), state(3, 30)],
    [transition(1, 2), transition(1, 3), transition(2, 4), transition(3, 4)],
    1
  )

  assert.equal(byId(result, 1).x, WORKFLOW_LAYOUT.marginX)
  assert.equal(byId(result, 2).x, byId(result, 3).x)
  assert.equal(byId(result, 4).x - byId(result, 2).x, WORKFLOW_LAYOUT.layerGap)
  assert.equal(byId(result, 2).y, 80)
  assert.equal(byId(result, 3).y, 200)
  assert.equal(byId(result, 1).y, 140)
  assert.equal(byId(result, 4).y, 140)
  assert.ok(Math.abs(byId(result, 2).y - byId(result, 3).y) >= WORKFLOW_LAYOUT.rowGap)
}

{
  const result = layoutWorkflowNodes(
    [state(1), state(2), state(3), state(4)],
    [transition(1, 2), transition(2, 3), transition(3, 2), transition(3, 4)],
    1
  )

  assert.equal(byId(result, 2).x, 320)
  assert.equal(byId(result, 3).x, 560)
  assert.equal(byId(result, 4).x, 800)
}

{
  const result = layoutWorkflowNodes(
    [state(1), state(2), state(10), state(11), state(20)],
    [transition(1, 2), transition(10, 11)],
    1
  )
  const mainBottom = Math.max(byId(result, 1).y, byId(result, 2).y)

  assert.ok(byId(result, 10).y > mainBottom)
  assert.equal(byId(result, 11).x - byId(result, 10).x, WORKFLOW_LAYOUT.layerGap)
  assert.ok(byId(result, 20).y > byId(result, 11).y)
}

{
  const result = layoutWorkflowNodes(
    [state('10', 10), state('2', 10), state('1', 5)],
    [transition('1', '2')],
    'missing'
  )

  assert.equal(byId(result, '1').x, WORKFLOW_LAYOUT.marginX)
  assert.ok(byId(result, '10').y > byId(result, '1').y)
}

{
  const result = layoutWorkflowNodes(
    [state(1), state(2)],
    [transition(1, 999), transition(999, 2), transition(1, 2)],
    1
  )

  assert.equal(byId(result, 2).x - byId(result, 1).x, WORKFLOW_LAYOUT.layerGap)
}

assert.deepEqual(layoutWorkflowNodes([], [], 1), [])

{
  const states = [state(2, 20, { metadata: { locked: true } }), state(1, 10)]
  const transitions = [transition(1, 2)]
  const statesSnapshot = structuredClone(states)
  const transitionsSnapshot = structuredClone(transitions)

  const first = layoutWorkflowNodes(states, transitions, 1)
  const second = layoutWorkflowNodes(states, transitions, 1)

  assert.deepEqual(first, second)
  assert.deepEqual(states, statesSnapshot)
  assert.deepEqual(transitions, transitionsSnapshot)
  assert.notEqual(first[0], states[0])
  assert.deepEqual(byId(first, 2).metadata, { locked: true })
  assert.equal(byId(first, 2).name, 'State 2')
}

{
  const result = layoutWorkflowNodes(
    [state(3, 10), state(2, 10), state(1, 0)],
    [transition(1, 3), transition(1, 2)],
    1
  )

  assert.ok(byId(result, 2).y < byId(result, 3).y)
  assert.ok(byId(result, 2).x - byId(result, 1).x >= WORKFLOW_LAYOUT.layerGap)
  assert.ok(byId(result, 3).y - byId(result, 2).y >= WORKFLOW_LAYOUT.rowGap)
}

console.log('workflow auto layout tests passed')
