import assert from 'node:assert/strict'

import { DEFAULT_BUG_TYPE_KEY, toBugTypeOptions } from './bugTypeOptions.js'

assert.equal(DEFAULT_BUG_TYPE_KEY, 'code_issue')
assert.deepEqual(
  toBugTypeOptions([
    { type_key: 'code_issue', display_name: '代码问题', is_real_bug: true, default_target_status: 'fixing' }
  ]),
  [
    {
      value: 'code_issue',
      label: '代码问题',
      isRealBug: true,
      defaultTargetStatus: 'fixing'
    }
  ]
)

console.log('bugTypeOptions tests passed')
