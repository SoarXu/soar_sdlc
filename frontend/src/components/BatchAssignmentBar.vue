<template>
  <div v-if="selectedRows.length" class="batch-assignment-bar">
    <span class="batch-assignment-count">已选 {{ selectedRows.length }} 项</span>
    <el-button type="primary" :disabled="!candidateUsers.length || submitting" @click="dialogVisible = true">指派给</el-button>
    <span v-if="!candidateUsers.length" class="batch-assignment-hint">所选记录没有共同可指派人员</span>

    <el-dialog v-model="dialogVisible" title="批量指派" width="460px" append-to-body :close-on-click-modal="!submitting">
      <el-form label-position="top">
        <el-form-item label="目标处理人" required>
          <el-select v-model="nextOwnerId" filterable placeholder="请选择处理人">
            <el-option v-for="user in candidateUsers" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="reasonRequired" label="代处理原因" required>
          <el-input v-model="delegateReason" type="textarea" :rows="3" maxlength="500" show-word-limit />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button :disabled="submitting" @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">确认指派</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { executeWorkflowBulkAssignment } from '../api/workflowRuntime'
import {
  eligibleAssigneeIds,
  isBatchAssignmentReasonRequired,
  toBatchAssignmentItems
} from '../utils/batchAssignmentSelection'

const props = defineProps({
  objectType: { type: String, required: true },
  projectId: { type: Number, default: null },
  selectedRows: { type: Array, default: () => [] },
  users: { type: Array, default: () => [] }
})

const emit = defineEmits(['completed', 'error'])
const dialogVisible = ref(false)
const nextOwnerId = ref(null)
const delegateReason = ref('')
const submitting = ref(false)
const candidateUserIds = computed(() => eligibleAssigneeIds(props.selectedRows))
const candidateUsers = computed(() => props.users.filter((user) => candidateUserIds.value.includes(user.id)))
const reasonRequired = computed(() => isBatchAssignmentReasonRequired(props.selectedRows))

watch(() => props.selectedRows, (rows) => {
  if (!rows.length) {
    dialogVisible.value = false
    nextOwnerId.value = null
    delegateReason.value = ''
  }
}, { deep: true })

async function submit() {
  if (!nextOwnerId.value) return ElMessage.warning('请选择目标处理人')
  if (reasonRequired.value && !delegateReason.value.trim()) return ElMessage.warning('请填写代处理原因')
  submitting.value = true
  try {
    const { data } = await executeWorkflowBulkAssignment({
      object_type: props.objectType,
      project_id: props.projectId,
      next_owner_id: nextOwnerId.value,
      delegate_reason: delegateReason.value.trim() || null,
      items: toBatchAssignmentItems(props.selectedRows)
    })
    dialogVisible.value = false
    nextOwnerId.value = null
    delegateReason.value = ''
    ElMessage.success(`已指派 ${data.completed_count} 项`)
    emit('completed', data)
  } catch (error) {
    emit('error', error)
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.batch-assignment-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 32px;
  padding: 8px 0 0;
}

.batch-assignment-count {
  color: var(--el-text-color-regular);
  font-size: 13px;
}

.batch-assignment-hint {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

@media (max-width: 720px) {
  .batch-assignment-bar {
    flex-wrap: wrap;
  }
}
</style>
