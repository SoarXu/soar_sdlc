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
  const points = pathPoints(path)
  return points.slice(1).map((point, index) => ({ from: points[index], to: point }))
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
