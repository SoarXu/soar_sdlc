import assert from 'node:assert/strict'

import {
  createWorkflowElkGraph,
  convertWorkflowElkResult,
  layoutWorkflowWithElk
} from './workflowElkLayout.js'

const states = [
  { id: 1, status_name: 'Pending', sort_order: 10, x: 500, y: 300, enabled: true },
  { id: 2, status_name: 'Processing', sort_order: 20, x: 100, y: 100, enabled: true },
  { id: '2', status_name: 'Confirmation', sort_order: 30, x: 200, y: 200, enabled: true },
  { id: 3, status_name: 'Completed', sort_order: 40, x: 300, y: 300, enabled: true },
  { id: 4, status_name: 'Retired', sort_order: 50, x: 400, y: 400, enabled: false }
]

const transitions = [
  { id: 11, action_name: 'Start', sort_order: 10, from_state_id: 1, to_state_id: 2 },
  { id: 12, action_name: 'Confirm', sort_order: 20, from_state_id: 2, to_state_id: '2' },
  { id: 13, action_name: 'Complete', sort_order: 30, from_state_id: '2', to_state_id: 3 },
  { id: 14, action_name: 'Return', sort_order: 40, from_state_id: 3, to_state_id: 1 },
  { id: 15, action_name: 'Add note', sort_order: 50, from_state_id: 1, to_state_id: 1 },
  { id: 16, action_name: 'Retired route', sort_order: 60, from_state_id: 4, to_state_id: 1 },
  { id: 17, action_name: 'Missing route', sort_order: 70, from_state_id: 99, to_state_id: 1 }
]

const statesSnapshot = structuredClone(states)
const transitionsSnapshot = structuredClone(transitions)
const graph = createWorkflowElkGraph(states, transitions, 1)

assert.deepEqual(graph.layoutOptions, {
  'elk.algorithm': 'layered',
  'elk.direction': 'RIGHT',
  'elk.edgeRouting': 'ORTHOGONAL',
  'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
  'elk.layered.crossingMinimization.greedySwitch.type': 'TWO_SIDED',
  'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
  'elk.layered.nodePlacement.bk.edgeStraightening': 'IMPROVE_STRAIGHTNESS',
  'elk.layered.spacing.nodeNodeBetweenLayers': '180',
  'elk.spacing.nodeNode': '80',
  'elk.spacing.edgeNode': '24',
  'elk.spacing.edgeEdge': '16',
  'elk.padding': '[top=80,left=80,bottom=80,right=80]'
})
assert.equal(graph.children.length, 4)
assert.equal(graph.edges.length, 4)
assert.equal(new Set(graph.children.map((node) => node.id)).size, 4)
assert.notEqual(graph.children[1].id, graph.children[2].id)
assert.ok(graph.children.every((node) => node.width === 118 && node.height === 42))
assert.equal(graph.children[0].layoutOptions['elk.layered.layering.layerConstraint'], 'FIRST')
assert.ok(graph.children.every((node) => node.layoutOptions['elk.portConstraints'] === 'FIXED_ORDER'))
assert.ok(graph.children.flatMap((node) => node.ports).every((port) => (
  port.width === 0 && port.height === 0
)))
assert.ok(graph.edges.every((edge) => edge.sources.length === 1 && edge.targets.length === 1))
assert.equal(new Set(graph.edges.flatMap((edge) => [...edge.sources, ...edge.targets])).size, 8)
assert.ok(graph.edges.every((edge) => edge.labels[0].width === 80 && edge.labels[0].height === 26))
assert.equal(graph.edges[0].labels[0].text, 'Start')
assert.equal(
  graph.children.find((node) => node.id === graph.edges[0].sources[0].split('/port/')[0])
    .ports.find((port) => port.id === graph.edges[0].sources[0])
    .layoutOptions['elk.port.side'],
  'EAST'
)
assert.deepEqual(createWorkflowElkGraph(states, transitions, 1), graph)
assert.deepEqual(states, statesSnapshot)
assert.deepEqual(transitions, transitionsSnapshot)

const [firstNodeId, secondNodeId] = graph.children.map((node) => node.id)
const firstEdgeId = graph.edges[0].id
const elkResult = {
  ...structuredClone(graph),
  children: [
    { ...graph.children[0], x: 80, y: 80 },
    { ...graph.children[1], x: 380, y: 80 },
    { ...graph.children[2], x: 680, y: 200 },
    { ...graph.children[3], x: 980, y: 200 }
  ],
  edges: graph.edges.map((edge, index) => ({
    ...edge,
    sections: index === 0
      ? [{
          id: `${edge.id}/section`,
          startPoint: { x: 198, y: 101 },
          bendPoints: [
            { x: 260, y: 101 },
            { x: 260, y: 151 },
            { x: 350, y: 151 },
            { x: 350, y: 101 }
          ],
          endPoint: { x: 380, y: 101 }
        }]
      : []
  }))
}

const converted = convertWorkflowElkResult(elkResult, states, transitions)
assert.deepEqual(converted.states.map(({ id, x, y }) => ({ id, x, y })), [
  { id: 1, x: 80, y: 80 },
  { id: 2, x: 380, y: 80 },
  { id: '2', x: 680, y: 200 },
  { id: 3, x: 980, y: 200 },
  { id: 4, x: 80, y: 362 }
])
assert.deepEqual(converted.transitions[0].diagram_config, {
  version: 1,
  routing_mode: 'generated',
  source_anchor: { side: 'right', ratio: 0.5 },
  target_anchor: { side: 'left', ratio: 0.5 },
  waypoints: [
    { x: 260, y: 101 },
    { x: 260, y: 151 },
    { x: 350, y: 151 },
    { x: 350, y: 101 }
  ]
})
assert.equal(converted.transitions[1].diagram_config, null)
assert.equal(Object.hasOwn(converted.transitions[4], 'diagram_config'), false)
assert.deepEqual(states, statesSnapshot)
assert.deepEqual(transitions, transitionsSnapshot)
assert.equal(firstNodeId, graph.children[0].id)
assert.equal(secondNodeId, graph.children[1].id)
assert.equal(firstEdgeId, graph.edges[0].id)

const tooManyBends = []
let point = { x: 198, y: 101 }
for (let index = 0; index < 34; index += 1) {
  point = index % 2 === 0
    ? { x: point.x + 5, y: point.y }
    : { x: point.x, y: point.y === 101 ? 111 : 101 }
  tooManyBends.push(point)
}
tooManyBends.push({ x: 350, y: point.y }, { x: 350, y: 101 })
const overflowResult = structuredClone(elkResult)
overflowResult.edges[0].sections[0] = {
  startPoint: { x: 198, y: 101 },
  bendPoints: tooManyBends,
  endPoint: { x: 380, y: 101 }
}
assert.equal(
  convertWorkflowElkResult(overflowResult, states, transitions).transitions[0].diagram_config,
  null
)

let receivedGraph = null
const layoutResult = await layoutWorkflowWithElk(states, transitions, 1, {
  layout: async (input) => {
    receivedGraph = input
    return elkResult
  }
})
assert.deepEqual(receivedGraph, graph)
assert.deepEqual(layoutResult, converted)

await assert.rejects(
  layoutWorkflowWithElk(states, transitions, 1, { layout: async () => ({ id: 'invalid' }) }),
  /invalid elk layout result/i
)

console.log('workflow ELK layout tests passed')
