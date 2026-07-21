import assert from 'node:assert/strict'

import { workflowGraphSnapshot } from './workflowGraphSnapshot.js'

const graph = {
  definitionId: 17,
  objectType: 'requirement',
  initialStateId: 1,
  states: [
    { id: 1, status_name: 'Pending', x: 80, y: 80, enabled: true },
    { id: 2, status_name: 'Processing', x: 380, y: 80, enabled: true }
  ],
  transitions: [
    {
      id: 11,
      action_name: 'Start',
      from_state_id: 1,
      to_state_id: 2,
      diagram_config: {
        version: 1,
        routing_mode: 'generated',
        source_anchor: { side: 'right', ratio: 0.5 },
        target_anchor: { side: 'left', ratio: 0.5 },
        waypoints: [{ x: 250, y: 101 }]
      }
    },
    { id: 12, action_name: 'Return', from_state_id: 2, to_state_id: 1 }
  ]
}

const original = structuredClone(graph)
const baseline = workflowGraphSnapshot(graph)
assert.equal(typeof baseline, 'string')
assert.deepEqual(graph, original)

for (const changed of [
  { ...graph, definitionId: 18 },
  { ...graph, objectType: 'task' },
  { ...graph, initialStateId: 2 },
  { ...graph, states: graph.states.map((state) => state.id === 1 ? { ...state, x: 81 } : state) },
  { ...graph, states: graph.states.map((state) => state.id === 1 ? { ...state, status_name: 'Ready' } : state) },
  { ...graph, transitions: [...graph.transitions].reverse() },
  {
    ...graph,
    transitions: graph.transitions.map((transition) => transition.id === 11
      ? {
          ...transition,
          diagram_config: {
            ...transition.diagram_config,
            waypoints: [{ x: 260, y: 101 }]
          }
        }
      : transition)
  }
]) {
  assert.notEqual(workflowGraphSnapshot(changed), baseline)
}

const reorderedKeys = {
  transitions: graph.transitions.map((transition) => transition.id === 11
    ? {
        diagram_config: {
          waypoints: [{ y: 101, x: 250 }],
          target_anchor: { ratio: 0.5, side: 'left' },
          source_anchor: { ratio: 0.5, side: 'right' },
          routing_mode: 'generated',
          version: 1
        },
        to_state_id: 2,
        from_state_id: 1,
        action_name: 'Start',
        id: 11
      }
    : {
        to_state_id: transition.to_state_id,
        from_state_id: transition.from_state_id,
        action_name: transition.action_name,
        id: transition.id
      }),
  states: graph.states.map((state) => ({
    enabled: state.enabled,
    y: state.y,
    x: state.x,
    status_name: state.status_name,
    id: state.id
  })),
  initialStateId: 1,
  objectType: 'requirement',
  definitionId: 17
}
assert.equal(workflowGraphSnapshot(reorderedKeys), baseline)

console.log('workflow graph snapshot tests passed')

