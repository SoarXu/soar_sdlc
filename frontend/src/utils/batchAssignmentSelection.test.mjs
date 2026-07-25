import assert from 'node:assert/strict'

import {
  batchAssignmentTransition,
  canSelectForBatchAssignment,
  eligibleAssigneeIds,
  isBatchAssignmentReasonRequired,
  toBatchAssignmentItems
} from './batchAssignmentSelection.js'

function row(id, projectId, transition) {
  return { id, project_id: projectId, transitions: transition ? [transition] : [] }
}

const assignToTwo = {
  transition_id: 31,
  bulk_assignment: { supported: true, requires_delegate_reason: false, eligible_assignee_ids: [2, 5] }
}
const assignToOne = {
  transition_id: 32,
  bulk_assignment: { supported: true, requires_delegate_reason: true, eligible_assignee_ids: [5, 8] }
}

const first = row(101, 10, assignToTwo)
const second = row(102, 10, assignToOne)
const otherProject = row(103, 11, assignToTwo)
const unsupported = row(104, 10, { transition_id: 33, bulk_assignment: { supported: false, eligible_assignee_ids: [] } })
const requirement = { ...first, object_type: 'requirement' }
const task = { ...second, object_type: 'task' }

assert.equal(batchAssignmentTransition(first), assignToTwo)
assert.equal(batchAssignmentTransition(unsupported), null)
assert.equal(canSelectForBatchAssignment(first, []), true)
assert.equal(canSelectForBatchAssignment(second, [first]), true)
assert.equal(canSelectForBatchAssignment(otherProject, [first]), false)
assert.equal(canSelectForBatchAssignment(task, [requirement]), false)
assert.equal(canSelectForBatchAssignment(unsupported, []), false)
assert.deepEqual(eligibleAssigneeIds([first, second]), [5])
assert.equal(isBatchAssignmentReasonRequired([first, second]), true)
assert.deepEqual(toBatchAssignmentItems([first, second]), [
  { id: 101, transition_id: 31 },
  { id: 102, transition_id: 32 }
])

console.log('batch assignment selection tests passed')
