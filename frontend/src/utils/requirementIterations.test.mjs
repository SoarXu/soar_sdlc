import assert from 'node:assert/strict'
import {
  deliveryIterations,
  requirementIterationLabel,
  requirementIterationOptions
} from './requirementIterations.js'

const projects = [{ id: 1 }, { id: 2, parent_id: 1 }, { id: 3, parent_id: 1 }]
const items = [
  { id: 10, name: 'Parent start', state_category: 'start', project_ids: [1] },
  { id: 11, name: 'Child active', state_category: 'normal', project_ids: [2] },
  { id: 12, name: 'Child closed', state_category: 'terminal', project_ids: [2] },
  { id: 13, name: 'Sibling start', state_category: 'start', project_ids: [3] }
]

assert.deepEqual(deliveryIterations(items), items)
assert.deepEqual(
  requirementIterationOptions(projects[1], projects, items).map((item) => item.id),
  [10, 11]
)
assert.equal(requirementIterationLabel(items[1]), 'Child active')
