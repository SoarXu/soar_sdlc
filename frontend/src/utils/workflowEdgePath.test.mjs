import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import * as workflowEdgePath from './workflowEdgePath.js'

const {
  addWorkflowReservation,
  buildWorkflowEdgeView,
  buildWorkflowEdgeViews,
  createWorkflowReservationIndex,
  queryWorkflowReservations
} = workflowEdgePath

assert.equal(typeof createWorkflowReservationIndex, 'function')
assert.equal(typeof addWorkflowReservation, 'function')
assert.equal(typeof queryWorkflowReservations, 'function')

{
  const index = createWorkflowReservationIndex(128)
  const longSegment = { id: 'long', from: { x: 0, y: 64 }, to: { x: 400, y: 64 } }
  const boundarySegment = { id: 'boundary', from: { x: 128, y: 0 }, to: { x: 128, y: 128 } }
  const farSegment = { id: 'far', from: { x: 800, y: 800 }, to: { x: 900, y: 800 } }
  const crossingLabel = { id: 'crossing', left: 120, top: 120, right: 136, bottom: 136 }
  const farLabel = { id: 'far-label', left: 800, top: 800, right: 820, bottom: 820 }

  ;[longSegment, boundarySegment, farSegment].forEach((segment) => {
    addWorkflowReservation(index, 'pathSegments', segment)
  })
  ;[crossingLabel, farLabel].forEach((rectangle) => {
    addWorkflowReservation(index, 'labelRectangles', rectangle)
  })

  assert.deepEqual(
    queryWorkflowReservations(index, 'pathSegments', {
      left: 300, top: 60, right: 310, bottom: 70
    }),
    [longSegment]
  )
  assert.deepEqual(
    queryWorkflowReservations(index, 'pathSegments', {
      left: 128, top: 60, right: 128, bottom: 70
    }),
    [longSegment, boundarySegment]
  )
  assert.deepEqual(
    queryWorkflowReservations(index, 'labelRectangles', {
      left: 128, top: 128, right: 128, bottom: 128
    }),
    [crossingLabel]
  )
}

const source = { x: 100, y: 100 }

{
  const target = { x: 320, y: 100 }
  const edge = buildWorkflowEdgeView(source, target)
  assert.deepEqual(edge.start, { x: 218, y: 121 })
  assert.deepEqual(edge.end, { x: 320, y: 121 })
}

{
  const target = { x: 160, y: 260 }
  const edge = buildWorkflowEdgeView(source, target)
  assert.deepEqual(edge.start, { x: 159, y: 142 })
  assert.deepEqual(edge.end, { x: 219, y: 260 })
  assert.match(edge.path, /L 159 185/)
  assert.match(edge.path, /L 219 260$/)
}

{
  const target = { x: 40, y: 260 }
  const edge = buildWorkflowEdgeView(source, target)
  assert.deepEqual(edge.start, { x: 159, y: 142 })
  assert.deepEqual(edge.end, { x: 99, y: 260 })
}

const transitionKey = (transition) => transition.id

{
  const states = [
    { id: 'left', x: 80, y: 120 },
    { id: 'right', x: 420, y: 120 },
    { id: 'lower', x: 80, y: 420 }
  ]
  const views = [
    buildWorkflowEdgeView(states[0], states[1]),
    ...buildWorkflowEdgeViews(states, [
      { id: 'forward-bounds', from_state_id: 'left', to_state_id: 'right' },
      { id: 'backward-bounds', from_state_id: 'right', to_state_id: 'left' },
      { id: 'vertical-bounds', from_state_id: 'left', to_state_id: 'lower' },
      { id: 'self-loop-bounds', from_state_id: 'lower', to_state_id: 'lower' }
    ], transitionKey)
  ]

  views.forEach(assertEdgeBoundsContainGeometry)
}

{
  const states = [
    { id: 'source', x: 40, y: 100 },
    { id: 'target', x: 360, y: 100 }
  ]
  const transitions = [
    { id: 'later', from_state_id: 'source', to_state_id: 'target', sort_order: 20 },
    { id: 'earlier', from_state_id: 'source', to_state_id: 'target', sort_order: 10 }
  ]
  const edges = buildWorkflowEdgeViews(states, transitions, transitionKey)

  assert.deepEqual(edges.map((edge) => edge.key), ['earlier', 'later'])
  assert.notEqual(edges[0].path, edges[1].path)
  assert.notDeepEqual(
    [edges[0].labelX, edges[0].labelY],
    [edges[1].labelX, edges[1].labelY]
  )
  edges.forEach((edge) => {
    assert.deepEqual(edge.start, { x: 158, y: 121 })
    assert.deepEqual(edge.end, { x: 360, y: 121 })
  })
}

{
  const states = [
    { id: 'target', x: 40, y: 100 },
    { id: 'source', x: 360, y: 100 }
  ]
  const transitions = [
    { id: 'return-2', from_state_id: 'source', to_state_id: 'target', sort_order: 20 },
    { id: 'return-1', from_state_id: 'source', to_state_id: 'target', sort_order: 10 }
  ]
  const edges = buildWorkflowEdgeViews(states, transitions, transitionKey)
  const routeBottoms = edges.map((edge) => Math.max(...pathPoints(edge.path).map(({ y }) => y)))

  assert.ok(routeBottoms.every((bottom) => bottom > 142))
  assert.equal(routeBottoms[1] - routeBottoms[0], 36)
  edges.forEach((edge) => {
    assert.deepEqual(edge.start, { x: 419, y: 142 })
    assert.deepEqual(edge.end, { x: 99, y: 142 })
  })
}

{
  const states = [
    { id: 'target', x: 40, y: 500 },
    { id: 'source', x: 360, y: 100 }
  ]
  const [edge] = buildWorkflowEdgeViews(states, [
    { id: 'steep-return', from_state_id: 'source', to_state_id: 'target' }
  ], transitionKey)

  assert.deepEqual(edge.start, { x: 419, y: 142 })
  assert.deepEqual(edge.end, { x: 99, y: 542 })
  assert.ok(Math.max(...pathPoints(edge.path).map(({ y }) => y)) > 542)
}

{
  const states = [
    { id: 'target', x: 80, y: 140 },
    { id: 'source', x: 320, y: 80 },
    { id: 'sibling', x: 320, y: 200 }
  ]
  const [edge] = buildWorkflowEdgeViews(states, [
    { id: 'sibling-return', from_state_id: 'source', to_state_id: 'target' }
  ], transitionKey)

  assert.deepEqual(edge.start, { x: 379, y: 122 })
  assert.deepEqual(edge.end, { x: 139, y: 182 })
  assert.ok(Math.max(...pathPoints(edge.path).map(({ y }) => y)) > 242)
  assertPathClearsRectangle(edge.path, expandedNodeRectangle(states[2]))
}

{
  const states = [
    { id: 'source', x: 40, y: 100 },
    { id: 'target', x: 360, y: 500 }
  ]
  const [edge] = buildWorkflowEdgeViews(states, [
    { id: 'steep-forward', from_state_id: 'source', to_state_id: 'target' }
  ], transitionKey)

  assert.deepEqual(edge.start, { x: 158, y: 121 })
  assert.deepEqual(edge.end, { x: 360, y: 521 })
}

{
  const states = [
    { id: 'upper', x: 100, y: 100 },
    { id: 'lower', x: 100, y: 300 }
  ]
  const [edge] = buildWorkflowEdgeViews(states, [
    { id: 'down', from_state_id: 'upper', to_state_id: 'lower' }
  ], transitionKey)
  const segments = pathSegments(edge.path)

  assert.deepEqual(edge.start, { x: 159, y: 142 })
  assert.deepEqual(edge.end, { x: 159, y: 300 })
  assert.ok(segments.every(({ from, to }) => to.y >= from.y))
  assert.ok(segments.every(({ from, to }) => from.x !== to.x || from.y !== to.y))
}

{
  const states = [
    { id: 'source', x: 100, y: 0 },
    { id: 'middle', x: 100, y: 140 },
    { id: 'target', x: 100, y: 300 }
  ]
  const [edge] = buildWorkflowEdgeViews(states, [
    { id: 'vertical-around-middle', from_state_id: 'source', to_state_id: 'target' }
  ], transitionKey)

  assert.deepEqual(edge.start, { x: 159, y: 42 })
  assert.deepEqual(edge.end, { x: 159, y: 300 })
  assertPathClearsRectangle(edge.path, expandedNodeRectangle(states[1]))
}

{
  const states = [
    { id: 1, x: 100, y: 0 },
    { id: 2, x: 100, y: 400 },
    { id: 3, x: 181, y: 200 }
  ]
  const [edge] = buildWorkflowEdgeViews(states, [
    { id: 'vertical-label-obstacle', from_state_id: 1, to_state_id: 2 }
  ], transitionKey)
  const labelRectangle = {
    left: edge.labelX - 40,
    top: edge.labelY - 13,
    right: edge.labelX + 40,
    bottom: edge.labelY + 13
  }

  assert.deepEqual(edge.start, { x: 159, y: 42 })
  assert.deepEqual(edge.end, { x: 159, y: 400 })
  assertPathClearsRectangle(edge.path, expandedNodeRectangle(states[2]))
  assert.equal(rectanglesIntersect(labelRectangle, nodeRectangle(states[2])), false)
}

{
  const states = [
    { id: 'source', x: 100, y: 0 },
    { id: 'middle', x: 100, y: 140 },
    { id: 'target', x: 100, y: 300 }
  ]
  const transitions = Array.from({ length: 4 }, (_, index) => ({
    id: `vertical-parallel-${index + 1}`,
    from_state_id: 'source',
    to_state_id: 'target',
    sort_order: (index + 1) * 10
  }))
  const edges = buildWorkflowEdgeViews(states, transitions, transitionKey)

  assert.equal(new Set(edges.map((edge) => edge.path)).size, edges.length)
  assert.equal(
    new Set(edges.map((edge) => `${edge.labelX}:${edge.labelY}`)).size,
    edges.length
  )
  const labelRectangles = edges.map((edge) => ({
    left: edge.labelX - 40,
    top: edge.labelY - 13,
    right: edge.labelX + 40,
    bottom: edge.labelY + 13
  }))
  for (let left = 0; left < labelRectangles.length; left += 1) {
    for (let right = left + 1; right < labelRectangles.length; right += 1) {
      assert.equal(rectanglesIntersect(labelRectangles[left], labelRectangles[right]), false)
    }
    for (let other = 0; other < edges.length; other += 1) {
      if (left === other) continue
      assertPathClearsRectangle(edges[left].path, labelRectangles[other])
    }
  }
  edges.forEach((edge) => {
    assertPathClearsRectangle(edge.path, expandedNodeRectangle(states[1]))
    assert.ok(labelDistanceToPath(edge) <= 1)
    const labelRectangle = {
      left: edge.labelX - 40,
      top: edge.labelY - 13,
      right: edge.labelX + 40,
      bottom: edge.labelY + 13
    }
    states.forEach((state) => {
      assert.equal(rectanglesIntersect(labelRectangle, nodeRectangle(state)), false)
    })
  })
}

{
  const states = [
    { id: 'a1', x: 100, y: 0 },
    { id: 'b1', x: 100, y: 300 },
    { id: 'obstacle', x: 100, y: 600 },
    { id: 'b2', x: 100, y: 900 },
    { id: 'a2', x: 100, y: 1200 }
  ]
  const edges = buildWorkflowEdgeViews(states, [
    { id: 'a1-to-a2', from_state_id: 'a1', to_state_id: 'a2' },
    { id: 'b1-to-b2', from_state_id: 'b1', to_state_id: 'b2' }
  ], transitionKey)
  const labelRectangles = edges.map((edge) => ({
    left: edge.labelX - 40,
    top: edge.labelY - 13,
    right: edge.labelX + 40,
    bottom: edge.labelY + 13
  }))

  assert.notEqual(edges[0].path, edges[1].path)
  assert.notDeepEqual(
    [edges[0].labelX, edges[0].labelY],
    [edges[1].labelX, edges[1].labelY]
  )
  assert.equal(rectanglesIntersect(labelRectangles[0], labelRectangles[1]), false)
  assertPathClearsRectangle(edges[0].path, labelRectangles[1])
  assertPathClearsRectangle(edges[1].path, labelRectangles[0])
  edges.forEach((edge) => {
    states
      .filter((state) => (
        state.id !== edge.transition.from_state_id &&
        state.id !== edge.transition.to_state_id
      ))
      .forEach((state) => {
        assertPathClearsRectangle(edge.path, expandedNodeRectangle(state))
      })
  })
}

assertVerticalColumnClusterTracks(
  [100, 100.0009, 100.0018],
  [76, 124.0009, 100.0018],
  'anchor-span'
)
assertVerticalColumnClusterTracks(
  [100, 100.00101],
  [100, 100.00101],
  'clearly-over-epsilon'
)
assertVerticalColumnReservations(-0.0004, 0.0004, 'signed-zero-boundary')
assertVerticalColumnReservations(100.00049, 100.00051, 'rounding-boundary')
assertVerticalColumnReservations(159, 159.001, 'exact-epsilon-boundary')

{
  const states = [
    { id: 'source', x: 100, y: 0 },
    { id: 'middle', x: 100, y: 140 },
    { id: 'left-wall', x: -100, y: 20 },
    { id: 'right-wall', x: 220, y: 20 },
    { id: 'target', x: 100, y: 300 }
  ]
  const [edge] = buildWorkflowEdgeViews(states, [
    { id: 'vertical-internal-channel', from_state_id: 'source', to_state_id: 'target' }
  ], transitionKey)

  assert.deepEqual(edge.start, { x: 159, y: 42 })
  assert.deepEqual(edge.end, { x: 159, y: 300 })
  states.slice(1, 4).forEach((state) => {
    assertPathClearsRectangle(edge.path, expandedNodeRectangle(state))
  })
}

{
  const states = [
    { id: 'upper', x: 100, y: 100 },
    { id: 'lower', x: 100, y: 300 }
  ]
  const [edge] = buildWorkflowEdgeViews(states, [
    { id: 'up', from_state_id: 'lower', to_state_id: 'upper' }
  ], transitionKey)
  const segments = pathSegments(edge.path)

  assert.deepEqual(edge.start, { x: 159, y: 300 })
  assert.deepEqual(edge.end, { x: 159, y: 142 })
  assert.ok(segments.every(({ from, to }) => to.y <= from.y))
  assert.ok(segments.every(({ from, to }) => from.x !== to.x || from.y !== to.y))
}

{
  const states = [
    { id: 'a', x: 100, y: 0 },
    { id: 'b', x: 100, y: 300 }
  ]
  const edges = buildWorkflowEdgeViews(states, [
    { id: 'a-to-b', from_state_id: 'a', to_state_id: 'b' },
    { id: 'b-to-a', from_state_id: 'b', to_state_id: 'a' }
  ], transitionKey)
  const labels = edges.map((edge) => ({
    left: edge.labelX - 40,
    top: edge.labelY - 13,
    right: edge.labelX + 40,
    bottom: edge.labelY + 13
  }))

  assert.notEqual(edges[0].path, edges[1].path)
  assert.notDeepEqual(
    [edges[0].labelX, edges[0].labelY],
    [edges[1].labelX, edges[1].labelY]
  )
  assert.equal(rectanglesIntersect(labels[0], labels[1]), false)
  assertPathClearsRectangle(edges[0].path, labels[1])
  assertPathClearsRectangle(edges[1].path, labels[0])
}

{
  const states = [
    { id: 'start', x: 40, y: 100 },
    { id: 'skipped', x: 240, y: 100 },
    { id: 'finish', x: 480, y: 100 }
  ]
  const [edge] = buildWorkflowEdgeViews(states, [
    { id: 'long', from_state_id: 'start', to_state_id: 'finish', sort_order: 10 }
  ], transitionKey)
  const skippedWithClearance = { left: 220, top: 80, right: 378, bottom: 162 }

  assert.ok(pathSegments(edge.path).every((segment) => (
    !segmentIntersectsRectangle(segment, skippedWithClearance)
  )))
}

{
  const states = [
    { id: 'start', x: 40, y: 100 },
    { id: 'near-start', x: 200, y: 100 },
    { id: 'finish', x: 480, y: 100 }
  ]
  const [edge] = buildWorkflowEdgeViews(states, [
    { id: 'near-start-long', from_state_id: 'start', to_state_id: 'finish' }
  ], transitionKey)

  assertPathClearsRectangle(edge.path, { left: 180, top: 80, right: 338, bottom: 162 })
}

{
  const states = [
    { id: 'start', x: 40, y: 100 },
    { id: 'near-finish', x: 340, y: 100 },
    { id: 'finish', x: 480, y: 100 }
  ]
  const [edge] = buildWorkflowEdgeViews(states, [
    { id: 'near-finish-long', from_state_id: 'start', to_state_id: 'finish' }
  ], transitionKey)

  assertPathClearsRectangle(edge.path, { left: 320, top: 80, right: 478, bottom: 162 })
}

{
  const states = [
    { id: 'source', x: 0, y: 0 },
    { id: 'upper', x: 100, y: -100 },
    { id: 'lower', x: 100, y: 100 },
    { id: 'target', x: 500, y: 0 }
  ]
  const [edge] = buildWorkflowEdgeViews(states, [
    { id: 'source-side-obstacles', from_state_id: 'source', to_state_id: 'target' }
  ], transitionKey)

  states.slice(1, 3).forEach((state) => {
    assertPathClearsRectangle(edge.path, expandedNodeRectangle(state))
  })
}

{
  const states = [
    { id: 'source', x: 0, y: 0 },
    { id: 'upper', x: 400, y: -100 },
    { id: 'lower', x: 400, y: 100 },
    { id: 'target', x: 500, y: 0 }
  ]
  const [edge] = buildWorkflowEdgeViews(states, [
    { id: 'target-side-obstacles', from_state_id: 'source', to_state_id: 'target' }
  ], transitionKey)

  states.slice(1, 3).forEach((state) => {
    assertPathClearsRectangle(edge.path, expandedNodeRectangle(state))
  })
}

{
  const states = [
    { id: 'source', x: 0, y: 0 },
    { id: 'source-upper', x: 100, y: -100 },
    { id: 'source-lower', x: 100, y: 100 },
    { id: 'target-upper', x: 360, y: -100 },
    { id: 'target-lower', x: 360, y: 100 },
    { id: 'target', x: 500, y: 0 }
  ]
  const [edge] = buildWorkflowEdgeViews(states, [
    { id: 'internal-forward-channels', from_state_id: 'source', to_state_id: 'target' }
  ], transitionKey)

  assert.ok(edge)
  states.slice(1, 5).forEach((state) => {
    assertPathClearsRectangle(edge.path, expandedNodeRectangle(state))
  })
}

{
  const states = [
    { id: 'source', x: 0, y: 0 },
    { id: 'near', x: 130, y: 0 },
    { id: 'target', x: 500, y: 0 }
  ]
  const transitions = [
    { id: 'insufficient-clearance', from_state_id: 'source', to_state_id: 'target' },
    { id: 'unaffected-edge', from_state_id: 'near', to_state_id: 'target' }
  ]
  const first = buildWorkflowEdgeViews(states, transitions, transitionKey)
  const second = buildWorkflowEdgeViews(states, transitions, transitionKey)

  assert.equal(first.length, transitions.length)
  assert.ok(first.every((edge) => edge.path.length > 0))
  assert.deepEqual(first, second)
  const closeEdge = first.find((edge) => edge.transition.id === 'insufficient-clearance')
  assertPathClearsRectangle(closeEdge.path, {
    left: 130,
    top: 0,
    right: 248,
    bottom: 42
  })
}

{
  const states = [
    { id: 'source', x: 0, y: 0 },
    { id: 'overlap', x: 100, y: 0 },
    { id: 'target', x: 500, y: 0 }
  ]
  const transitions = [
    { id: 'overlapping-clearance', from_state_id: 'source', to_state_id: 'target' },
    { id: 'overlap-unaffected-edge', from_state_id: 'overlap', to_state_id: 'target' }
  ]
  const edges = buildWorkflowEdgeViews(states, transitions, transitionKey)

  assert.equal(edges.length, transitions.length)
  assert.ok(edges.every((edge) => edge.path.length > 0))
}

{
  const obstacles = Array.from({ length: 150 }, (_, index) => ({
    id: `obstacle-${index}`,
    x: 200 + index * 50,
    y: index % 2 === 0 ? -100 : 100
  }))
  const states = [
    { id: 'source', x: 0, y: 0 },
    ...obstacles,
    { id: 'target', x: 8000, y: 0 }
  ]
  const edges = buildWorkflowEdgeViews(states, [
    { id: 'large-obstacle-route', from_state_id: 'source', to_state_id: 'target' }
  ], transitionKey)

  assert.equal(edges.length, 1)
  assert.ok(edges[0].path.length > 0)
}

{
  const states = [
    { id: 0, x: -150, y: 241 },
    { id: 6, x: -135, y: 543 },
    { id: 10, x: 9, y: 568 },
    { id: 11, x: -81, y: 243 }
  ]
  let edges

  assert.doesNotThrow(() => {
    edges = buildWorkflowEdgeViews(states, [
      { id: 'normalization-regression', from_state_id: 6, to_state_id: 10 }
    ], transitionKey)
  })
  assert.equal(edges.length, 1)
  assertFiniteEdgeView(edges[0])
  assert.ok(labelDistanceToPath(edges[0]) <= 1)
}

{
  let seed = 0x5eed1234
  const random = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0
    return seed / 0x100000000
  }

  for (let graphIndex = 0; graphIndex < 12; graphIndex += 1) {
    const states = Array.from({ length: 6 }, (_, index) => ({
      id: index,
      x: Math.floor(random() * 700) - 350,
      y: Math.floor(random() * 700) - 350
    }))
    const transitions = Array.from({ length: 8 }, (_, index) => {
      const from = Math.floor(random() * states.length)
      const to = (from + 1 + Math.floor(random() * (states.length - 1))) % states.length
      return {
        id: `fuzz-${graphIndex}-${index}`,
        from_state_id: from,
        to_state_id: to,
        sort_order: index * 10
      }
    })
    let edges

    assert.doesNotThrow(() => {
      edges = buildWorkflowEdgeViews(states, transitions, transitionKey)
    })
    assert.equal(edges.length, transitions.length)
    edges.forEach(assertFiniteEdgeView)
  }
}

{
  const sourceCode = readFileSync(new URL('./workflowEdgePath.js', import.meta.url), 'utf8')
  assert.doesNotMatch(sourceCode, /safeStartChannels\.flatMap/)
  assert.match(
    sourceCode,
    /function segmentIntersectsRectangle[\s\S]*?segmentBoundsIntersectRectangle\(from, to, rectangle\)/
  )
}

{
  const state = { id: 'loop', x: 100, y: 100 }
  const [edge] = buildWorkflowEdgeViews([state], [
    { id: 'loop-edge', from_state_id: 'loop', to_state_id: 'loop', sort_order: 10 }
  ], transitionKey)
  const points = pathPoints(edge.path)

  assert.deepEqual(edge.start, { x: 218, y: 121 })
  assert.deepEqual(edge.end, { x: 159, y: 142 })
  assert.ok(Math.max(...points.map(({ x }) => x)) > 218)
  assert.ok(Math.max(...points.map(({ y }) => y)) > 142)
  assert.ok(edge.labelX > 218 || edge.labelY > 142)
  assertPathClearsRectangle(edge.path, {
    left: edge.labelX - 40,
    top: edge.labelY - 13,
    right: edge.labelX + 40,
    bottom: edge.labelY + 13
  })
}

{
  const states = [
    { id: 1, x: 320, y: 140 },
    { id: 2, x: 560, y: 200 }
  ]
  const transitions = Array.from({ length: 3 }, (_, index) => ({
    id: `obstructed-loop-${index + 1}`,
    from_state_id: 1,
    to_state_id: 1,
    sort_order: index * 10
  }))
  const edges = buildWorkflowEdgeViews(states, transitions, transitionKey)

  assert.equal(new Set(edges.map((edge) => edge.path)).size, edges.length)
  assert.equal(
    new Set(edges.map((edge) => `${edge.labelX}:${edge.labelY}`)).size,
    edges.length
  )
  edges.forEach((edge) => {
    assertPathClearsRectangle(edge.path, expandedNodeRectangle(states[1]))
    const labelRectangle = {
      left: edge.labelX - 40,
      top: edge.labelY - 13,
      right: edge.labelX + 40,
      bottom: edge.labelY + 13
    }
    assert.equal(rectanglesIntersect(labelRectangle, nodeRectangle(states[1])), false)
  })
}

{
  const states = [{ id: 'reserved-loop-node', x: 100, y: 100 }]
  const transitions = Array.from({ length: 5 }, (_, index) => ({
    id: `reserved-loop-${index + 1}`,
    from_state_id: 'reserved-loop-node',
    to_state_id: 'reserved-loop-node',
    sort_order: index * 10
  }))
  const first = buildWorkflowEdgeViews(states, transitions, transitionKey)
  const second = buildWorkflowEdgeViews(states, transitions, transitionKey)
  const labelRectangles = first.map((edge) => ({
    left: edge.labelX - 40,
    top: edge.labelY - 13,
    right: edge.labelX + 40,
    bottom: edge.labelY + 13
  }))

  assert.deepEqual(first, second)
  assert.equal(new Set(first.map((edge) => edge.path)).size, first.length)
  assert.equal(
    new Set(first.map((edge) => `${edge.labelX}:${edge.labelY}`)).size,
    first.length
  )
  for (let left = 0; left < first.length; left += 1) {
    for (let right = left + 1; right < first.length; right += 1) {
      assert.equal(rectanglesIntersect(labelRectangles[left], labelRectangles[right]), false)
    }
    for (let other = 0; other < first.length; other += 1) {
      if (left === other) continue
      assertPathClearsRectangle(first[left].path, labelRectangles[other])
    }
  }
}

{
  const states = [
    { id: 'pending-assignment', x: 80, y: 140 },
    { id: 'in-processing', x: 320, y: 140 },
    { id: 'canceled', x: 560, y: 200 }
  ]
  const transitions = [
    {
      id: 'claim',
      from_state_id: 'pending-assignment',
      to_state_id: 'in-processing',
      sort_order: 10
    },
    {
      id: 'assign',
      from_state_id: 'pending-assignment',
      to_state_id: 'in-processing',
      sort_order: 20
    },
    ...Array.from({ length: 3 }, (_, index) => ({
      id: `pending-command-${index + 1}`,
      from_state_id: 'pending-assignment',
      to_state_id: 'pending-assignment',
      sort_order: (index + 1) * 10
    })),
    {
      id: 'cancel',
      from_state_id: 'in-processing',
      to_state_id: 'canceled',
      sort_order: 10
    },
    {
      id: 'transfer',
      from_state_id: 'in-processing',
      to_state_id: 'in-processing',
      sort_order: 10
    }
  ]
  const edges = buildWorkflowEdgeViews(states, transitions, transitionKey)
  const labelRectangles = edges.map((edge) => ({
    left: edge.labelX - 40,
    top: edge.labelY - 13,
    right: edge.labelX + 40,
    bottom: edge.labelY + 13
  }))

  for (let left = 0; left < edges.length; left += 1) {
    for (let right = left + 1; right < edges.length; right += 1) {
      assert.equal(rectanglesIntersect(labelRectangles[left], labelRectangles[right]), false)
    }
    for (let other = 0; other < edges.length; other += 1) {
      if (left === other) continue
      assertPathClearsRectangle(edges[left].path, labelRectangles[other])
    }
    states.forEach((state) => {
      if (state.id === edges[left].transition.from_state_id ||
        state.id === edges[left].transition.to_state_id) return
      assertPathClearsRectangle(edges[left].path, expandedNodeRectangle(state))
      assert.equal(rectanglesIntersect(labelRectangles[left], nodeRectangle(state)), false)
    })
  }
}

{
  const states = [
    { id: 'left-loop', x: 100, y: 100 },
    { id: 'right-loop', x: 500, y: 100 }
  ]
  const edges = buildWorkflowEdgeViews(states, [
    { id: 'left-self', from_state_id: 'left-loop', to_state_id: 'left-loop' },
    { id: 'right-self', from_state_id: 'right-loop', to_state_id: 'right-loop' }
  ], transitionKey)
  const relativeWidths = edges.map((edge, index) => (
    Math.max(...pathPoints(edge.path).map(({ x }) => x)) - states[index].x
  ))

  assert.equal(relativeWidths[0], relativeWidths[1])
}

{
  const states = [
    { id: 1, x: 40, y: 100 },
    { id: 2, x: 360, y: 100 }
  ]
  const transitions = [
    { id: 'valid', from_state_id: 1, to_state_id: 2, sort_order: 10 },
    { id: 'missing-source', from_state_id: 9, to_state_id: 2, sort_order: 20 },
    { id: 'missing-target', from_state_id: 1, to_state_id: 9, sort_order: 30 }
  ]
  const stateSnapshot = structuredClone(states)
  const transitionSnapshot = structuredClone(transitions)
  const first = buildWorkflowEdgeViews(states, transitions, transitionKey)
  const second = buildWorkflowEdgeViews(states, transitions, transitionKey)

  assert.deepEqual(first, second)
  assert.deepEqual(first.map((edge) => edge.key), ['valid'])
  assert.deepEqual(states, stateSnapshot)
  assert.deepEqual(transitions, transitionSnapshot)
}

{
  const states = [
    { id: 'a', x: 40, y: 100 },
    { id: 'b', x: 360, y: 100 },
    { id: 'c', x: 680, y: 100 }
  ]
  const transitions = [
    { id: 'duplicate', from_state_id: 'b', to_state_id: 'c', sort_order: 10 },
    { id: 'duplicate', from_state_id: 'a', to_state_id: 'c', sort_order: 20 },
    { id: 'duplicate', from_state_id: 'a', to_state_id: 'b', sort_order: 10 }
  ]
  const edges = buildWorkflowEdgeViews(states, transitions, transitionKey)

  assert.deepEqual(edges.map(({ transition }) => (
    `${transition.from_state_id}-${transition.to_state_id}`
  )), ['a-b', 'a-c', 'b-c'])
  assert.equal(new Set(edges.map((edge) => edge.key)).size, edges.length)
}

function pathPoints(path) {
  const commandPattern = /([MLQ])\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)(?:\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?))?/g
  const points = []
  let match

  while ((match = commandPattern.exec(path))) {
    points.push({ x: Number(match[2]), y: Number(match[3]) })
    if (match[1] === 'Q') points.push({ x: Number(match[4]), y: Number(match[5]) })
  }

  return points
}

function assertEdgeBoundsContainGeometry(edge) {
  assert.ok(edge.bounds, 'edge view must expose bounds')
  const geometry = [
    ...pathPoints(edge.path),
    { x: edge.labelX - 40, y: edge.labelY - 13 },
    { x: edge.labelX + 40, y: edge.labelY + 13 }
  ]
  geometry.forEach((point) => {
    assert.ok(edge.bounds.left <= point.x, `left bound excludes ${point.x}`)
    assert.ok(edge.bounds.top <= point.y, `top bound excludes ${point.y}`)
    assert.ok(edge.bounds.right >= point.x, `right bound excludes ${point.x}`)
    assert.ok(edge.bounds.bottom >= point.y, `bottom bound excludes ${point.y}`)
  })
}

function pathSegments(path) {
  const commandPattern = /([MLQ])\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)(?:\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?))?/g
  const segments = []
  let current
  let match

  while ((match = commandPattern.exec(path))) {
    const command = match[1]
    const firstPoint = { x: Number(match[2]), y: Number(match[3]) }
    if (command === 'M') {
      current = firstPoint
    } else if (command === 'L') {
      segments.push({ from: current, to: firstPoint })
      current = firstPoint
    } else {
      const end = { x: Number(match[4]), y: Number(match[5]) }
      let previous = current
      for (let step = 1; step <= 16; step += 1) {
        const ratio = step / 16
        const point = quadraticPoint(current, firstPoint, end, ratio)
        segments.push({ from: previous, to: point })
        previous = point
      }
      current = end
    }
  }

  return segments
}

function quadraticPoint(start, control, end, ratio) {
  const inverse = 1 - ratio
  return {
    x: inverse * inverse * start.x + 2 * inverse * ratio * control.x + ratio * ratio * end.x,
    y: inverse * inverse * start.y + 2 * inverse * ratio * control.y + ratio * ratio * end.y
  }
}

function assertPathClearsRectangle(path, rectangle) {
  assert.ok(pathSegments(path).every((segment) => (
    !segmentIntersectsRectangle(segment, rectangle)
  )))
}

function assertFiniteEdgeView(edge) {
  assert.ok(edge.path.length > 0)
  assert.doesNotMatch(edge.path, /NaN|Infinity/)
  assert.ok([
    edge.labelX,
    edge.labelY,
    edge.start.x,
    edge.start.y,
    edge.end.x,
    edge.end.y,
    ...pathPoints(edge.path).flatMap((point) => [point.x, point.y])
  ].every(Number.isFinite))
}

function labelDistanceToPath(edge) {
  const label = { x: edge.labelX, y: edge.labelY }
  return Math.min(...pathSegments(edge.path).map((segment) => (
    pointToSegmentDistance(label, segment)
  )))
}

function pointToSegmentDistance(point, { from, to }) {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const lengthSquared = dx * dx + dy * dy
  if (!lengthSquared) return Math.hypot(point.x - from.x, point.y - from.y)
  const ratio = Math.max(0, Math.min(1, (
    (point.x - from.x) * dx + (point.y - from.y) * dy
  ) / lengthSquared))
  return Math.hypot(
    point.x - (from.x + ratio * dx),
    point.y - (from.y + ratio * dy)
  )
}

function expandedNodeRectangle(node) {
  return {
    left: node.x - 20,
    top: node.y - 20,
    right: node.x + 138,
    bottom: node.y + 62
  }
}

function nodeRectangle(node) {
  return {
    left: node.x,
    top: node.y,
    right: node.x + 118,
    bottom: node.y + 42
  }
}

function rectanglesIntersect(left, right) {
  return left.right >= right.left && left.left <= right.right &&
    left.bottom >= right.top && left.top <= right.bottom
}

function assertVerticalColumnReservations(firstCenterX, secondCenterX, idPrefix) {
  const states = [
    { id: `${idPrefix}-a1`, x: firstCenterX - 59, y: 0 },
    { id: `${idPrefix}-b1`, x: secondCenterX - 59, y: 300 },
    { id: `${idPrefix}-left-bound`, x: -59, y: 600 },
    { id: `${idPrefix}-obstacle`, x: (firstCenterX + secondCenterX) / 2 - 59, y: 600 },
    { id: `${idPrefix}-right-bound`, x: 241, y: 600 },
    { id: `${idPrefix}-b2`, x: secondCenterX - 59, y: 900 },
    { id: `${idPrefix}-a2`, x: firstCenterX - 59, y: 1200 }
  ]
  const transitions = [
    {
      id: `${idPrefix}-a1-to-a2`,
      from_state_id: `${idPrefix}-a1`,
      to_state_id: `${idPrefix}-a2`
    },
    {
      id: `${idPrefix}-b1-to-b2`,
      from_state_id: `${idPrefix}-b1`,
      to_state_id: `${idPrefix}-b2`
    }
  ]
  const edges = buildWorkflowEdgeViews(states, transitions, transitionKey)
  const reorderedEdges = buildWorkflowEdgeViews(
    states,
    [...transitions].reverse(),
    transitionKey
  )
  const labelRectangles = edges.map((edge) => ({
    left: edge.labelX - 40,
    top: edge.labelY - 13,
    right: edge.labelX + 40,
    bottom: edge.labelY + 13
  }))

  assert.deepEqual(edges, reorderedEdges)
  assert.equal(rectanglesIntersect(labelRectangles[0], labelRectangles[1]), false)
  assertPathClearsRectangle(edges[0].path, labelRectangles[1])
  assertPathClearsRectangle(edges[1].path, labelRectangles[0])
  edges.forEach((edge) => {
    states
      .filter((state) => (
        state.id !== edge.transition.from_state_id &&
        state.id !== edge.transition.to_state_id
      ))
      .forEach((state) => {
        assertPathClearsRectangle(edge.path, expandedNodeRectangle(state))
      })
  })
}

function assertVerticalColumnClusterTracks(centerXs, expectedLabelXs, idPrefix) {
  const states = centerXs.flatMap((centerX, index) => ([
    { id: `${idPrefix}-${index}-from`, x: centerX - 59, y: index * 300 },
    { id: `${idPrefix}-${index}-to`, x: centerX - 59, y: index * 300 + 120 }
  ]))
  const transitions = centerXs.map((_, index) => ({
    id: `${idPrefix}-${index}`,
    from_state_id: `${idPrefix}-${index}-from`,
    to_state_id: `${idPrefix}-${index}-to`
  }))
  const edges = buildWorkflowEdgeViews(states, transitions, transitionKey)
  const reorderedEdges = buildWorkflowEdgeViews(
    states,
    [...transitions].reverse(),
    transitionKey
  )

  assert.deepEqual(edges, reorderedEdges)
  edges.forEach((edge, index) => {
    assert.ok(
      Math.abs(edge.labelX - expectedLabelXs[index]) < 1e-9,
      `${idPrefix} edge ${index} expected labelX ${expectedLabelXs[index]}, got ${edge.labelX}`
    )
  })
}

function segmentIntersectsRectangle({ from, to }, rectangle) {
  let minimum = 0
  let maximum = 1
  const dx = to.x - from.x
  const dy = to.y - from.y
  const boundaries = [
    [-dx, from.x - rectangle.left],
    [dx, rectangle.right - from.x],
    [-dy, from.y - rectangle.top],
    [dy, rectangle.bottom - from.y]
  ]

  for (const [direction, distance] of boundaries) {
    if (direction === 0 && distance < 0) return false
    if (direction === 0) continue
    const ratio = distance / direction
    if (direction < 0) minimum = Math.max(minimum, ratio)
    else maximum = Math.min(maximum, ratio)
    if (minimum > maximum) return false
  }

  return true
}

console.log('workflowEdgePath tests passed')
