<template>
  <el-dialog :model-value="visible" title="代码评审" width="920px" append-to-body @update:model-value="emit('update:visible', $event)">
    <div v-loading="loading" class="work-item-review-dialog">
      <CommitDiffViewer
        v-if="context?.has_diff"
        :diff-text="context.diff_text || ''"
        :diff-json="context.diff_json"
      />
      <el-empty v-else description="未找到 Git Diff 片段" :image-size="80" />
      <el-form label-position="top" class="work-item-review-decision-form">
        <el-form-item label="不通过理由" required>
          <el-input v-model="remark" type="textarea" :rows="3" maxlength="1000" show-word-limit placeholder="代码评审不通过时必填" />
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button v-if="rejectAction" :type="buttonType(rejectAction)" :loading="deciding === 'reject'" @click="decide(rejectAction)">
        {{ rejectAction.action_name }}
      </el-button>
      <el-button v-if="approveAction" :type="buttonType(approveAction)" :loading="deciding === 'approve'" @click="decide(approveAction)">
        {{ approveAction.action_name }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { decideWorkItemReview, fetchWorkItemReviewContext } from '../api/devops'
import { fetchWorkflowTransitions } from '../api/workflowRuntime'
import { showActionError } from '../utils/actionFeedback'
import CommitDiffViewer from './CommitDiffViewer.vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  objectType: { type: String, required: true },
  objectId: { type: Number, required: true }
})
const emit = defineEmits(['update:visible', 'decided'])
const loading = ref(false)
const deciding = ref('')
const context = ref(null)
const remark = ref('')
const reviewActions = ref([])
const approveAction = computed(() => reviewActions.value.find((action) => action.action_key === 'approve_review'))
const rejectAction = computed(() => reviewActions.value.find((action) => action.action_key === 'reject_review'))

watch(() => [props.visible, props.objectType, props.objectId], async ([visible]) => {
  if (!visible || !props.objectType || !props.objectId) return
  loading.value = true
  remark.value = ''
  reviewActions.value = []
  try {
    const [contextResponse, transitionsResponse] = await Promise.all([
      fetchWorkItemReviewContext(props.objectType, props.objectId),
      fetchWorkflowTransitions(props.objectType, props.objectId)
    ])
    context.value = contextResponse.data
    reviewActions.value = transitionsResponse.data || []
  } catch (error) {
    context.value = null
    showActionError(error, '加载评审信息失败')
    emit('update:visible', false)
  } finally {
    loading.value = false
  }
}, { immediate: true })

function buttonType(action) {
  return action?.button_type || action?.ui_config?.button_type || 'primary'
}

async function decide(action) {
  if (!context.value?.review_round?.id) return
  const decision = action.action_key === 'approve_review' ? 'approve' : 'reject'
  const value = remark.value.trim()
  if (decision === 'reject' && !value) {
    ElMessage.warning('请填写不通过理由')
    return
  }
  deciding.value = decision
  try {
    const { data } = await decideWorkItemReview(context.value.review_round.id, {
      decision,
      remark: decision === 'reject' ? value : null
    })
    ElMessage.success(decision === 'approve' ? '代码评审已通过' : '代码评审未通过')
    emit('update:visible', false)
    emit('decided', data)
  } catch (error) {
    showActionError(error, '代码评审失败')
  } finally {
    deciding.value = ''
  }
}
</script>

<style scoped>
.work-item-review-decision-form { margin-top: 16px; }
</style>
