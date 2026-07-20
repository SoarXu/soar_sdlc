import assert from 'node:assert/strict'

import { workflowActionColumnWidth } from './workflowActionColumn.js'

const width = workflowActionColumnWidth([
  [
    { transition_id: 1, action_name: '开始处理', list_display: 'primary', sort_order: 10 },
    { transition_id: 2, action_name: '提交验证', list_display: 'primary', sort_order: 20 },
    { transition_id: 3, action_name: '取消', list_display: 'more', sort_order: 10 }
  ],
  [{ transition_id: 4, action_name: '关闭', list_display: 'primary', sort_order: 10 }]
], { minWidth: 180, extraWidth: 80 })

assert.ok(width > 180)
assert.equal(workflowActionColumnWidth([], { minWidth: 220 }), 220)
assert.equal(workflowActionColumnWidth([[{ transition_id: 4, action_name: '关闭', list_display: 'more' }]], { minWidth: 180 }), 180)

console.log('workflow action column tests passed')
