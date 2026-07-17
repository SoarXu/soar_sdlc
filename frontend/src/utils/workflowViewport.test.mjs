import assert from 'node:assert/strict'
import { layoutWorkflowNodes } from './workflowAutoLayout.js'
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

console.log('workflowViewport tests passed')
