import assert from 'node:assert/strict'
import { layoutWorkflowNodes } from './workflowAutoLayout.js'
import { buildWorkflowEdgeViews } from './workflowEdgePath.js'
import {
  applyPanDelta,
  clampViewport,
  fitViewportToNodes,
  workflowCanvasSize
} from './workflowViewport.js'

const canvas = { width: 2400, height: 1400 }
const viewport = { width: 900, height: 540 }

{
  const nodes = [{ id: 1, x: 80, y: 80 }]
  const originalNodes = structuredClone(nodes)
  assert.deepEqual(workflowCanvasSize(nodes), canvas)
  assert.deepEqual(nodes, originalNodes)
  assert.deepEqual(workflowCanvasSize([]), canvas)
}

{
  const states = Array.from({ length: 20 }, (_, index) => ({
    id: index + 1,
    status_name: `状态${index + 1}`,
    x: 0,
    y: 0
  }))
  const transitions = Array.from({ length: 19 }, (_, index) => ({
    from_state_id: index + 1,
    to_state_id: index + 2
  }))
  const layout = layoutWorkflowNodes(states, transitions, 1)
  const rightmost = layout.reduce((current, node) => node.x > current.x ? node : current)
  const expandedCanvas = workflowCanvasSize(layout)
  const leftmostOffset = clampViewport({ x: -Infinity, y: 0 }, expandedCanvas, viewport)

  assert.ok(expandedCanvas.width >= rightmost.x + 118 + 160)
  assert.ok(rightmost.x + 118 + leftmostOffset.x <= viewport.width - 160)
}

{
  const states = Array.from({ length: 20 }, (_, index) => ({
    id: index + 1,
    status_name: `独立状态${index + 1}`,
    x: 0,
    y: 0
  }))
  const layout = layoutWorkflowNodes(states, [], 1)
  const bottommost = layout.reduce((current, node) => node.y > current.y ? node : current)
  const expandedCanvas = workflowCanvasSize(layout)
  const topmostOffset = clampViewport({ x: 0, y: -Infinity }, expandedCanvas, viewport)

  assert.ok(expandedCanvas.height >= bottommost.y + 42 + 120)
  assert.ok(bottommost.y + 42 + topmostOffset.y <= viewport.height - 120)
}

{
  const next = applyPanDelta({ x: 0, y: 0 }, { dx: -120, dy: -80 }, canvas, viewport)
  assert.deepEqual(next, { x: -120, y: -80 })
}

{
  const next = applyPanDelta({ x: -100, y: -100 }, { dx: 2600, dy: 2000 }, canvas, viewport)
  assert.deepEqual(next, { x: 450, y: 270 })
}

{
  const next = clampViewport({ x: -3000, y: -2000 }, canvas, viewport)
  assert.deepEqual(next, { x: -1500, y: -860 })
}

{
  const shrunk = clampViewport(
    { x: -4298, y: -2000 },
    { width: 2400, height: 1400 },
    { width: 980, height: 540 }
  )
  assert.deepEqual(shrunk, { x: -1420, y: -860 })
}

{
  const currentOffset = { x: -500, y: -300 }
  const expanded = clampViewport(
    currentOffset,
    { width: 5278, height: 4802 },
    { width: 980, height: 540 }
  )
  assert.deepEqual(expanded, currentOffset)
}

{
  const offsetAfterDrag = clampViewport(
    { x: -4298, y: 0 },
    { width: 5078, height: 1400 },
    { width: 980, height: 540 }
  )
  assert.deepEqual(offsetAfterDrag, { x: -4098, y: 0 })
}

{
  const next = fitViewportToNodes(
    [
      { x: 300, y: 200 },
      { x: 1200, y: 760 }
    ],
    canvas,
    viewport
  )
  assert.deepEqual(next, { x: -359, y: -231 })
}

{
  const next = fitViewportToNodes(
    [
      { x: 120, y: 80 },
      { x: 520, y: 240 }
    ],
    canvas,
    viewport
  )
  assert.deepEqual(next, { x: 71, y: 89 })
}

{
  const next = fitViewportToNodes([], canvas, viewport)
  assert.deepEqual(next, { x: 0, y: 0 })
}

{
  const nodes = [
    { id: 'target', x: 80, y: 1200 },
    { id: 'source', x: 520, y: 1200 }
  ]
  const transitions = Array.from({ length: 10 }, (_, index) => ({
    id: `return-${index + 1}`,
    from_state_id: 'source',
    to_state_id: 'target',
    sort_order: index
  }))
  const edgeViews = buildWorkflowEdgeViews(nodes, transitions, (transition) => transition.id)
  const edgeBottom = Math.max(...edgeViews.map((edge) => edge.bounds.bottom))
  const expandedCanvas = workflowCanvasSize(nodes, undefined, undefined, edgeViews)
  const bottomOffset = clampViewport(
    { x: 0, y: -Infinity },
    expandedCanvas,
    viewport
  )
  const nodeOnlyFit = fitViewportToNodes(nodes, expandedCanvas, viewport)
  const contentFit = fitViewportToNodes(nodes, expandedCanvas, viewport, edgeViews)

  assert.ok(edgeBottom > 1602, `expected label bounds below the 1602 path, got ${edgeBottom}`)
  assert.ok(expandedCanvas.height >= edgeBottom + 120)
  assert.ok(edgeBottom + bottomOffset.y <= viewport.height - 120)
  assert.notDeepEqual(contentFit, nodeOnlyFit)
  assert.deepEqual(contentFit, clampViewport(contentFit, expandedCanvas, viewport))
}

{
  const edgeViews = [{ bounds: { left: 400, top: 300, right: 600, bottom: 500 } }]
  assert.notDeepEqual(
    fitViewportToNodes([], canvas, viewport, edgeViews),
    { x: 0, y: 0 }
  )
}

console.log('workflowViewport tests passed')
