import assert from 'node:assert/strict'

import {
  anchorPointForNode,
  createManualDiagramConfig,
  diagramRoutePoints,
  generatedDiagramConfigFromView,
  isGeneratedDiagramRoute,
  isManualDiagramRoute,
  moveManualAnchor,
  moveManualSegment,
  normalizeManualWaypoints
} from './workflowManualRoute.js'

const from = { id: 1, x: 100, y: 100 }
const to = { id: 2, x: 360, y: 260 }

assert.deepEqual(
  anchorPointForNode(from, { side: 'bottom', ratio: 0.25 }),
  { x: 129.5, y: 142 }
)
assert.deepEqual(
  anchorPointForNode(from, { side: 'left', ratio: 0 }),
  { x: 100, y: 108 }
)

const initialView = {
  points: [
    { x: 159, y: 142 },
    { x: 159, y: 190 },
    { x: 419, y: 190 },
    { x: 419, y: 260 }
  ]
}
const manual = createManualDiagramConfig(initialView, from, to)
assert.deepEqual(manual, {
  version: 1,
  routing_mode: 'manual',
  source_anchor: { side: 'bottom', ratio: 0.5 },
  target_anchor: { side: 'top', ratio: 0.5 },
  waypoints: [{ x: 159, y: 190 }, { x: 419, y: 190 }]
})
assert.equal(isManualDiagramRoute(manual), true)
assert.equal(isGeneratedDiagramRoute(manual), false)
assert.deepEqual(diagramRoutePoints(from, to, manual), initialView.points)

const generated = { ...structuredClone(manual), routing_mode: 'generated' }
assert.equal(isManualDiagramRoute(generated), false)
assert.equal(isGeneratedDiagramRoute(generated), true)
assert.deepEqual(diagramRoutePoints(from, to, generated), initialView.points)
assert.equal(diagramRoutePoints(from, to, { ...manual, routing_mode: 'unknown' }), null)
assert.deepEqual(generatedDiagramConfigFromView(initialView, from, to), generated)

const movedTo = { ...to, x: 440, y: 300 }
assert.deepEqual(diagramRoutePoints(from, movedTo, manual), [
  { x: 159, y: 142 },
  { x: 159, y: 190 },
  { x: 499, y: 190 },
  { x: 499, y: 300 }
])

const movedSourceAnchor = moveManualAnchor(
  manual,
  'source',
  { x: 210, y: 118 },
  from,
  to
)
assert.equal(movedSourceAnchor.source_anchor.side, 'right')
assert.equal(movedSourceAnchor.source_anchor.ratio, 18 / 42)
assert.deepEqual(diagramRoutePoints(from, to, movedSourceAnchor), [
  { x: 218, y: 118 },
  { x: 246, y: 118 },
  { x: 246, y: 190 },
  { x: 419, y: 190 },
  { x: 419, y: 260 }
])

const movedSegment = moveManualSegment(manual, 1, { x: 250, y: 220 }, from, to)
assert.deepEqual(movedSegment.waypoints, [
  { x: 159, y: 220 },
  { x: 419, y: 220 }
])
assert.deepEqual(diagramRoutePoints(from, to, movedSegment), [
  { x: 159, y: 142 },
  { x: 159, y: 220 },
  { x: 419, y: 220 },
  { x: 419, y: 260 }
])

assert.deepEqual(normalizeManualWaypoints([
  { x: 10, y: 10 },
  { x: 10, y: 10 },
  { x: 20, y: 10 },
  { x: 30, y: 10 },
  { x: 30, y: 20 }
]), [
  { x: 10, y: 10 },
  { x: 30, y: 10 },
  { x: 30, y: 20 }
])

assert.equal(moveManualSegment(manual, 0, { x: 200, y: 200 }, from, to), null)
assert.equal(moveManualSegment(manual, 2, { x: 200, y: 200 }, from, to), null)

console.log('workflow manual route tests passed')
