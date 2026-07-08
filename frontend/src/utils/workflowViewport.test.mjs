import assert from 'node:assert/strict'
import {
  applyPanDelta,
  clampViewport,
  fitViewportToNodes
} from './workflowViewport.js'

const canvas = { width: 2400, height: 1400 }
const viewport = { width: 900, height: 540 }

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
