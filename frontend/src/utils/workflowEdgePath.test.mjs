import assert from 'node:assert/strict'
import { buildWorkflowEdgeView } from './workflowEdgePath.js'

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

console.log('workflowEdgePath tests passed')
