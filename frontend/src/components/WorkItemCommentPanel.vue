<template>
  <el-card shadow="never" class="detail-panel comment-panel">
    <template #header>
      <div class="detail-card-header">
        <span>评论</span>
        <el-tag type="info">{{ comments.length }}</el-tag>
      </div>
    </template>

    <WorkItemCommentComposer
      ref="commentComposer"
      :object-type="objectType"
      :object-id="objectId"
      :users="users"
      :loading="saving"
      @submit="submitComment"
    />

    <el-empty v-if="!comments.length" description="暂无评论" class="comment-empty" />
    <div v-else class="comment-list">
      <article v-for="comment in comments" :key="comment.id" class="comment-item">
        <header class="comment-item-head">
          <strong>{{ comment.author_name || `用户 #${comment.author_id}` }}</strong>
          <span>{{ formatDateTime(comment.create_time) }}</span>
        </header>
        <p class="comment-body">{{ comment.body }}</p>
        <div v-if="comment.mentions_metadata?.length" class="comment-mentions">
          <el-tag v-for="mention in comment.mentions_metadata" :key="mention.user_id" size="small" effect="plain">
            @{{ mention.display_name || mention.user_id }}
          </el-tag>
        </div>
      </article>
    </div>
  </el-card>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { createWorkItemComment, fetchWorkItemComments } from '../api/workItemComments'
import WorkItemCommentComposer from './WorkItemCommentComposer.vue'

const props = defineProps({
  objectType: { type: String, required: true },
  objectId: { type: Number, required: true },
  users: { type: Array, default: () => [] }
})

const comments = ref([])
const saving = ref(false)
const commentComposer = ref(null)

function formatDateTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : ''
}

async function loadComments() {
  if (!props.objectType || !props.objectId) return
  const { data } = await fetchWorkItemComments(props.objectType, props.objectId)
  comments.value = data.items || []
}

async function submitComment({ body, mentionedUserIds }) {
  saving.value = true
  try {
    await createWorkItemComment({
      object_type: props.objectType,
      object_id: props.objectId,
      body,
      mentioned_user_ids: mentionedUserIds
    })
    commentComposer.value?.clear()
    await loadComments()
    ElMessage.success('评论已保存')
  } finally {
    saving.value = false
  }
}

watch(() => [props.objectType, props.objectId], loadComments)
onMounted(loadComments)
</script>

<style scoped>
.comment-panel {
  margin-bottom: 0;
}

.comment-list {
  display: grid;
  gap: 12px;
}

.comment-item {
  padding: 12px;
  background: #f7f9fc;
  border: 1px solid #e1e7ef;
  border-radius: 6px;
}

.comment-item-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  color: #5f6f82;
  font-size: 12px;
}

.comment-body {
  margin: 0;
  color: #243047;
  white-space: pre-wrap;
}

.comment-mentions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
}

.comment-empty {
  padding: 24px 0 8px;
}
</style>
