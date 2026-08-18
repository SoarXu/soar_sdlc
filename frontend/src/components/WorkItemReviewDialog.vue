<template>
  <el-dialog :model-value="visible" title="评审" width="920px" append-to-body @update:model-value="emit('update:visible', $event)">
    <div v-loading="loading" class="work-item-review-dialog">
      <CommitDiffViewer
        v-if="context?.has_diff"
        :diff-text="context.diff_text || ''"
        :diff-json="context.diff_json"
      />
      <el-empty v-else description="未找到 Git Diff 片段" :image-size="80" />
      <el-form label-position="top" class="work-item-review-decision-form">
        <el-form-item label="不通过理由" required>
          <el-input v-model="remark" type="textarea" :rows="3" maxlength="1000" show-word-limit placeholder="评审不通过时必填" />
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="danger" :loading="deciding === 'reject'" @click="decide('reject')">评审不通过</el-button>
      <el-button type="success" :loading="deciding === 'approve'" @click="decide('approve')">评审通过</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { decideWorkItemReview, fetchWorkItemReviewContext } from '../api/devops'
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

watch(() => [props.visible, props.objectType, props.objectId], async ([visible]) => {
  if (!visible || !props.objectType || !props.objectId) return
  loading.value = true
  remark.value = ''
  try {
    const { data } = await fetchWorkItemReviewContext(props.objectType, props.objectId)
    context.value = data
  } catch (error) {
    context.value = null
    showActionError(error, '加载评审信息失败')
    emit('update:visible', false)
  } finally {
    loading.value = false
  }
}, { immediate: true })

async function decide(decision) {
  if (!context.value?.review_round?.id) return
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
    ElMessage.success(decision === 'approve' ? '评审已通过' : '评审已驳回')
    emit('update:visible', false)
    emit('decided', data)
  } catch (error) {
    showActionError(error, '评审失败')
  } finally {
    deciding.value = ''
  }
}
</script>

<style scoped>
.work-item-review-decision-form { margin-top: 16px; }
</style>
