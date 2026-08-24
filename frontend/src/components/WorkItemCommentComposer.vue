<template>
  <div class="comment-composer">
    <el-input
      ref="composerInput"
      v-model="draft.body"
      type="textarea"
      :rows="rows"
      :placeholder="placeholder"
      @input="handleBodyInput"
      @click="syncCursorPosition"
      @keyup="syncCursorPosition"
    />
    <div v-if="mentionSuggestions.length" class="comment-mention-picker">
      <span class="comment-mention-label">@用户</span>
      <button
        v-for="user in mentionSuggestions"
        :key="user.id"
        type="button"
        class="comment-mention-option"
        @click="selectMention(user)"
      >
        {{ user.full_name || user.username }}
      </button>
    </div>
    <el-select
      v-model="draft.mentionedUserIds"
      multiple
      filterable
      collapse-tags
      collapse-tags-tooltip
      placeholder="@用户"
    >
      <el-option v-for="user in mentionAudience" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
    </el-select>
    <div class="comment-actions">
      <el-button type="primary" :loading="loading" @click="submit">{{ submitLabel }}</el-button>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchWorkItemCommentMentionUsers } from '../api/workItemComments'

const props = defineProps({
  objectType: { type: String, default: '' },
  objectId: { type: Number, default: 0 },
  users: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  placeholder: { type: String, default: '补充处理信息' },
  rows: { type: Number, default: 4 },
  submitLabel: { type: String, default: '发表评论' }
})

const emit = defineEmits(['submit'])

const composerInput = ref(null)
const cursorPosition = ref(0)
const mentionUsers = ref([])
const draft = reactive({
  body: '',
  mentionedUserIds: []
})
const activeMention = computed(() => findActiveMention(draft.body, cursorPosition.value))
const mentionAudience = computed(() => (
  props.objectType && props.objectId ? mentionUsers.value : props.users
))
const mentionSuggestions = computed(() => {
  const mention = activeMention.value
  if (!mention) return []
  const query = mention.query.toLowerCase()
  return mentionAudience.value
    .filter((user) => {
      const displayName = `${user.full_name || ''} ${user.username || ''}`.toLowerCase()
      return !query || displayName.includes(query)
    })
    .slice(0, 6)
})

async function loadMentionUsers() {
  if (!props.objectType || !props.objectId) {
    mentionUsers.value = []
    return
  }
  try {
    const { data } = await fetchWorkItemCommentMentionUsers(props.objectType, props.objectId)
    mentionUsers.value = data || []
  } catch {
    mentionUsers.value = []
  }
}

function findActiveMention(text, position) {
  if (!text || position < 0) return null
  const beforeCursor = text.slice(0, position)
  const match = beforeCursor.match(/(^|\s)@([^\s@]*)$/)
  if (!match) return null
  return {
    start: beforeCursor.length - match[2].length - 1,
    end: beforeCursor.length,
    query: match[2] || ''
  }
}

function syncCursorPosition() {
  const textarea = composerInput.value?.textarea
  if (!textarea) return
  cursorPosition.value = textarea.selectionStart || 0
}

function handleBodyInput() {
  nextTick(syncCursorPosition)
}

async function selectMention(user) {
  const mention = activeMention.value
  if (!mention) return
  const displayName = user.full_name || user.username
  draft.body = `${draft.body.slice(0, mention.start)}@${displayName} ${draft.body.slice(mention.end)}`
  if (!draft.mentionedUserIds.includes(user.id)) {
    draft.mentionedUserIds = [...draft.mentionedUserIds, user.id]
  }
  await nextTick()
  const textarea = composerInput.value?.textarea
  const nextPosition = mention.start + displayName.length + 2
  if (textarea) {
    textarea.focus()
    textarea.setSelectionRange(nextPosition, nextPosition)
  }
  cursorPosition.value = nextPosition
}

function submit() {
  const body = draft.body.trim()
  if (!body) {
    ElMessage.warning('请填写评论内容')
    return
  }
  emit('submit', { body, mentionedUserIds: [...draft.mentionedUserIds] })
}

function clear() {
  draft.body = ''
  draft.mentionedUserIds = []
  cursorPosition.value = 0
}

defineExpose({ clear })

watch(() => [props.objectType, props.objectId], loadMentionUsers, { immediate: true })
</script>

<style scoped>
.comment-composer {
  display: grid;
  gap: 12px;
  margin-bottom: 16px;
}

.comment-actions {
  display: flex;
  justify-content: flex-end;
}

.comment-mention-picker {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.comment-mention-label {
  color: #5f6f82;
  font-size: 12px;
}

.comment-mention-option {
  padding: 4px 10px;
  color: #215b9a;
  background: #edf6ff;
  border: 1px solid #c7dcf3;
  border-radius: 6px;
  cursor: pointer;
}
</style>
