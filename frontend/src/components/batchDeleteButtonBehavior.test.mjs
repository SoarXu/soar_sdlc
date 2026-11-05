import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { computed, ref } from 'vue'
import { deleteSelectedRows } from '../utils/bulkDelete.js'
import { actionErrorMessage } from '../utils/permissions.js'

const source = await readFile(new URL('./BatchDeleteButton.vue', import.meta.url), 'utf8')
const script = source.match(/<script setup>([\s\S]*?)<\/script>/)[1].replace(/^import .*$/gm, '')
const createComponent = new Function(
  'computed', 'ref', 'ElMessage', 'ElMessageBox', 'actionErrorMessage', 'deleteSelectedRows', 'defineProps', 'defineEmits',
  `${script}\nreturn { confirmDelete, deleting }`
)

function setup({ allowed = true, cancel = false, failId = null } = {}) {
  const calls = [], confirmations = [], alerts = [], events = [], messages = []
  const props = {
    label: '需求', selectedRows: [{ id: 1, title: 'first' }, { id: 2, title: 'blocked' }],
    canDelete: () => allowed,
    deleteRow: async (id) => {
      calls.push(id)
      if (id === failId) throw { response: { data: { detail: '存在关联任务' } } }
    }
  }
  const component = createComponent(computed, ref, { success: (message) => messages.push(message) }, {
    confirm: async (message) => { confirmations.push(message); if (cancel) throw 'cancel' },
    alert: async (message) => alerts.push(message)
  }, actionErrorMessage, deleteSelectedRows, () => props, () => (event) => events.push(event))
  return { ...component, calls, confirmations, alerts, events, messages }
}

const denied = setup({ allowed: false })
await denied.confirmDelete()
assert.deepEqual(denied.confirmations, [])
assert.deepEqual(denied.calls, [], '无删除权限时不得发送删除请求')

const canceled = setup({ cancel: true })
await canceled.confirmDelete()
assert.deepEqual(canceled.calls, [], '取消确认后不得删除')

const success = setup()
await success.confirmDelete()
assert.match(success.confirmations[0], /2 条需求/)
assert.deepEqual(success.calls, [1, 2])
assert.deepEqual(success.events, ['completed'])
assert.match(success.messages[0], /已删除 2 条需求/)

const partial = setup({ failId: 2 })
await partial.confirmDelete()
assert.deepEqual(partial.calls, [1, 2])
assert.deepEqual(partial.events, ['completed'])
assert.match(partial.alerts[0], /成功 1 条，失败 1 条/)
assert.match(partial.alerts[0], /#2 blocked：存在关联任务/)
assert.deepEqual(partial.messages, [], '部分失败不得提示全部成功')
assert.equal(partial.deleting.value, false)

console.log('batch delete confirmation, permission and partial failure tests passed')
