<template>
  <el-button
    v-if="selectedRows.length"
    type="danger"
    plain
    :loading="deleting"
    :disabled="!allDeletable"
    :title="allDeletable ? '' : '所选记录包含无删除权限的项目'"
    @click="confirmDelete"
  >批量删除（{{ selectedRows.length }}）</el-button>
</template>

<script setup>
import { computed, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { actionErrorMessage } from '../utils/permissions'
import { deleteSelectedRows } from '../utils/bulkDelete'

const props = defineProps({
  selectedRows: { type: Array, default: () => [] },
  label: { type: String, required: true },
  deleteRow: { type: Function, required: true },
  canDelete: { type: Function, required: true }
})
const emit = defineEmits(['completed'])
const deleting = ref(false)
const allDeletable = computed(() => props.selectedRows.every(props.canDelete))

async function confirmDelete() {
  if (deleting.value || !props.selectedRows.length || !allDeletable.value) return
  try {
    await ElMessageBox.confirm(
      `确认删除选中的 ${props.selectedRows.length} 条${props.label}？删除后不可恢复。`,
      '批量删除',
      { type: 'warning', confirmButtonText: '删除', confirmButtonClass: 'el-button--danger' }
    )
  } catch {
    return
  }

  deleting.value = true
  try {
    const { deleted, failed } = await deleteSelectedRows(props.selectedRows, props.deleteRow)
    if (deleted.length) emit('completed')
    if (!failed.length) {
      ElMessage.success(`已删除 ${deleted.length} 条${props.label}`)
      return
    }
    const details = failed.slice(0, 8).map(({ row, error }) => {
      const detail = error?.response?.data?.detail
      const reason = actionErrorMessage(error) || (typeof detail === 'string' ? detail : '') || error?.message || '删除失败'
      return `#${row.id} ${String(row.title || row.name || '').slice(0, 30)}：${reason}`
    })
    if (failed.length > 8) details.push(`另有 ${failed.length - 8} 条失败`)
    await ElMessageBox.alert(
      `成功 ${deleted.length} 条，失败 ${failed.length} 条。${details.join('；')}`,
      '批量删除结果',
      { type: 'warning' }
    )
  } finally {
    deleting.value = false
  }
}
</script>
