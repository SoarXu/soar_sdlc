import assert from 'node:assert/strict'

import { loadCloseReasonMap } from './closeReasonTooltip.js'

const result = await loadCloseReasonMap([
  { id: 1, current_state_id: 10, state_category: 'terminal' },
  { id: 2, current_state_id: 20, state_category: 'normal' }
], async (id) => ({
  data: id === 1
    ? [{ id: 8, to_state_id: 10, reason: '完成说明', remark: '已经验收' }]
    : []
}))

assert.deepEqual(result, { 1: '完成说明<br>已经验收' })

console.log('close reason tooltip state identity tests passed')
