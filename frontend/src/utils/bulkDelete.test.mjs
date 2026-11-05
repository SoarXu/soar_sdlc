import assert from 'node:assert/strict'
import { deleteSelectedRows } from './bulkDelete.js'

const calls = []
const rows = [
  { id: 1, title: 'Parent' },
  { id: 2, title: 'Child', parent_task_id: 1 },
  { id: 3, title: 'Blocked' }
]

const result = await deleteSelectedRows(rows, async (id) => {
  calls.push(id)
  if (id === 3) throw new Error('cannot delete')
})

assert.deepEqual(calls, [2, 1, 3], 'selected child tasks must be deleted before their parents')
assert.deepEqual(result.deleted.map((row) => row.id), [2, 1])
assert.deepEqual(result.failed.map(({ row, error }) => [row.id, error.message]), [[3, 'cannot delete']])

console.log('bulk delete result handling passed')
