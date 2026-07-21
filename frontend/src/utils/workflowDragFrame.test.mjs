import assert from 'node:assert/strict'

import { createWorkflowDragFrame } from './workflowDragFrame.js'

const NODE_WIDTH = 118
const NODE_HEIGHT = 42

const states = [
  { id: 'source', x: 100, y: 100, enabled: true },
  { id: 'dragged', x: 360, y: 260, enabled: true },
  { id: 'target', x: 760, y: 100, enabled: true }
]
const transitions = [
  { id: 'incoming-auto', from_state_id: 'source', to_state_id: 'dragged' },
  { id: 'outgoing-auto', from_state_id: 'dragged', to_state_id: 'target' },
  {
    id: 'incoming-manual',
    from_state_id: 'source',
    to_state_id: 'dragged',
    diagram_config: {
      version: 1,
      routing_mode: 'manual',
      source_anchor: { side: 'bottom', ratio: 0.5 },
      target_anchor: { side: 'top', ratio: 0.5 },
      waypoints: [{ x: 159, y: 190 }, { x: 419, y: 190 }]
    }
  }
]

const statesSnapshot = structuredClone(states)
const transitionsSnapshot = structuredClone(transitions)
const frame = createWorkflowDragFrame(
  states,
  transitions,
  'dragged',
  { x: 640, y: 360 },
  (transition) => transition.id
)

assert.ok(frame)
const dragged = frame.states.find((state) => state.id === 'dragged')
assert.deepEqual({ x: dragged.x, y: dragged.y }, { x: 640, y: 360 })
assert.notEqual(dragged, states[1])
assert.equal(frame.states[0], states[0])
assert.equal(frame.states[2], states[2])

const incoming = frame.transitionViews.filter((edge) => edge.transition.to_state_id === 'dragged')
const outgoing = frame.transitionViews.filter((edge) => edge.transition.from_state_id === 'dragged')
assert.equal(incoming.length, 2)
assert.equal(outgoing.length, 1)
incoming.forEach((edge) => assert.ok(pointOnNodeBorder(edge.end, dragged)))
outgoing.forEach((edge) => assert.ok(pointOnNodeBorder(edge.start, dragged)))

assert.deepEqual(states, statesSnapshot)
assert.deepEqual(transitions, transitionsSnapshot)
assert.equal(createWorkflowDragFrame(states, transitions, 'missing', { x: 1, y: 2 }), null)
assert.equal(createWorkflowDragFrame(states, transitions, 'dragged', { x: NaN, y: 2 }), null)

function pointOnNodeBorder(point, node) {
  const withinX = point.x >= node.x && point.x <= node.x + NODE_WIDTH
  const withinY = point.y >= node.y && point.y <= node.y + NODE_HEIGHT
  return (withinX && (point.y === node.y || point.y === node.y + NODE_HEIGHT)) ||
    (withinY && (point.x === node.x || point.x === node.x + NODE_WIDTH))
}

console.log('workflow drag frame tests passed')
