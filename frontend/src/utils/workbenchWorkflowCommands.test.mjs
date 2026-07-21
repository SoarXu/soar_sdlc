import assert from 'node:assert/strict'

import { resolveWorkbenchWorkflowCommand } from './workbenchWorkflowCommands.js'

assert.deepEqual(
  resolveWorkbenchWorkflowCommand({ object_type: 'requirement', id: 3919 }, 'edit'),
  { kind: 'edit', objectType: 'requirement', objectId: 3919 }
)
assert.deepEqual(
  resolveWorkbenchWorkflowCommand({ object_type: 'task', id: 8 }, 'edit'),
  { kind: 'edit', objectType: 'task', objectId: 8 }
)
assert.deepEqual(
  resolveWorkbenchWorkflowCommand({ object_type: 'bug', id: 9 }, 'edit'),
  { kind: 'edit', objectType: 'bug', objectId: 9 }
)
assert.equal(resolveWorkbenchWorkflowCommand({ object_type: 'test_case', id: 7 }, 'edit'), null)
assert.equal(resolveWorkbenchWorkflowCommand({ object_type: 'task', id: 8 }, 'unknown'), null)
assert.equal(resolveWorkbenchWorkflowCommand({ object_type: 'bug', id: null }, 'edit'), null)

console.log('workbench workflow command tests passed')
