import assert from 'node:assert/strict'

import { TASK_BRANCH_OPTIONS, deriveTaskBranch } from './taskBranchRules.js'

assert.deepEqual(
  TASK_BRANCH_OPTIONS.map((item) => item.value),
  ['requirement_implementation', 'bug_fix', 'test_support', 'standalone_operation']
)

assert.equal(
  deriveTaskBranch({ requirementId: 42, currentType: 'standalone_operation' }),
  'requirement_implementation'
)
assert.equal(deriveTaskBranch({ requirementId: null, currentType: null }), 'standalone_operation')
assert.equal(deriveTaskBranch({ requirementId: null, currentType: 'test_support' }), 'test_support')

console.log('taskBranchRules tests passed')
