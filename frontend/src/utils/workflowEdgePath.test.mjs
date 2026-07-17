import assert from 'node:assert/strict'
import { buildWorkflowEdgeView, buildWorkflowEdgeViews } from './workflowEdgePath.js'

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

function expandedNodeRectangle(node) {
  return {
    left: node.x - 20,
    top: node.y - 20,
    right: node.x + 138,
    bottom: node.y + 62
  }
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
