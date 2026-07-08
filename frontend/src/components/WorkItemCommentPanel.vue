<template>
  <el-card shadow="never" class="detail-panel comment-panel">
    <template #header>
      <div class="detail-card-header">
        <span>评论</span>
        <el-tag type="info">{{ comments.length }}</el-tag>
      </div>
    </template>

    <div class="comment-composer">
      <el-input v-model="draft.body" type="textarea" :rows="4" placeholder="补充处理信息" />
      <el-select
        v-model="draft.mentionedUserIds"
        multiple
        filterable
        collapse-tags
        collapse-tags-tooltip
        placeholder="@用户"
      >
        <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
      </el-select>
      <div class="comment-actions">
        <el-button type="primary" :loading="saving" @click="submitComment">发表评论</el-button>
      </div>
    </div>

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
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { createWorkItemComment, fetchWorkItemComments } from '../api/workItemComments'

const props = defineProps({
  objectType: { type: String, required: true },
  objectId: { type: Number, required: true },
  users: { type: Array, default: () => [] }
})

const comments = ref([])
const saving = ref(false)
const draft = reactive({
  body: '',
  mentionedUserIds: []
})

function formatDateTime(value) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : ''
}

async function loadComments() {
  if (!props.objectType || !props.objectId) return
  const { data } = await fetchWorkItemComments(props.objectType, props.objectId)
  comments.value = data.items || []
}

async function submitComment() {
  if (!draft.body.trim()) {
    ElMessage.warning('请填写评论内容')
    return
  }
  saving.value = true
  try {
    await createWorkItemComment({
      object_type: props.objectType,
      object_id: props.objectId,
      body: draft.body.trim(),
      mentioned_user_ids: draft.mentionedUserIds
    })
    draft.body = ''
    draft.mentionedUserIds = []
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

.comment-composer {
  display: grid;
  gap: 12px;
  margin-bottom: 16px;
}

.comment-actions {
  display: flex;
  justify-content: flex-end;
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
