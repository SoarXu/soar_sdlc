import assert from 'node:assert/strict'

import { combineWorkflowDragViews } from './workflowDragViews.js'

const full = [
  { key: 'a', transition: { from_state_id: 1, to_state_id: 2 }, path: 'FULL-A' },
  { key: 'b', transition: { from_state_id: 2, to_state_id: 3 }, path: 'FULL-B' },
  { key: 'c', transition: { from_state_id: 4, to_state_id: 5 }, path: 'FULL-C' }
]
const preview = [
  { key: 'a', transition: full[0].transition, path: 'PREVIEW-A' },
  { key: 'b', transition: full[1].transition, path: 'PREVIEW-B' },
  { key: 'c', transition: full[2].transition, path: 'PREVIEW-C' }
]

{
  const fullSnapshot = structuredClone(full)
  const previewSnapshot = structuredClone(preview)
  const result = combineWorkflowDragViews(full, preview, 2)

  assert.deepEqual(result.map((item) => item.path), ['PREVIEW-A', 'PREVIEW-B', 'FULL-C'])
  assert.equal(result[0], preview[0])
  assert.equal(result[2], full[2])
  assert.deepEqual(full, fullSnapshot)
  assert.deepEqual(preview, previewSnapshot)
}

assert.equal(combineWorkflowDragViews(full, preview, null), full)

{
  const result = combineWorkflowDragViews(
    full.slice(0, 2),
    [...preview, { key: 'missing', transition: { from_state_id: 7, to_state_id: 8 }, path: 'PREVIEW-D' }],
    2
  )

  assert.deepEqual(result.map((item) => item.path), ['PREVIEW-A', 'PREVIEW-B', 'PREVIEW-C', 'PREVIEW-D'])
}

console.log('workflow drag view tests passed')
