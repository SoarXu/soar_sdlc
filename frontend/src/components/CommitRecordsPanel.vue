<template>
  <el-card shadow="never" class="detail-panel">
    <template #header>提交记录</template>
    <el-empty v-if="!commits.length" description="暂无提交记录" />
    <el-table v-else :data="commits" stripe>
      <el-table-column label="Commit" width="150">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDiff(row)">{{ row.short_sha || row.commit_sha }}</el-button>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="提交说明" min-width="240" />
      <el-table-column prop="branch_name" label="分支" width="130" />
      <el-table-column prop="author_name" label="提交人" width="130" />
      <el-table-column label="提交时间" width="180"><template #default="{ row }">{{ formatDateTime(row.committed_at) }}</template></el-table-column>
    </el-table>

    <el-dialog v-model="diffDialogVisible" title="Code Review Diff" width="920px">
      <div v-if="selectedCommit" class="commit-summary">
        <strong>{{ selectedCommit.short_sha || selectedCommit.commit_sha }}</strong>
        <span>{{ selectedCommit.title || selectedCommit.message }}</span>
      </div>
      <pre class="diff-viewer">{{ selectedCommit?.diff_text || formatDiffJson(selectedCommit?.diff_json) || '暂无 diff 内容' }}</pre>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'

import { fetchDevopsCommit, fetchDevopsCommits } from '../api/devops'

const props = defineProps({
  objectType: { type: String, required: true },
  objectId: { type: Number, required: true }
})

const commits = ref([])
const selectedCommit = ref(null)
const diffDialogVisible = ref(false)

function formatDateTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-' }
function formatDiffJson(value) { return value ? JSON.stringify(value, null, 2) : '' }

async function openDiff(row) {
  const { data } = await fetchDevopsCommit(row.id)
  selectedCommit.value = data
  diffDialogVisible.value = true
}

async function loadCommits() {
  if (!props.objectId) return
  const { data } = await fetchDevopsCommits({ object_type: props.objectType, object_id: props.objectId })
  commits.value = data
}

watch(() => [props.objectType, props.objectId], loadCommits)
onMounted(loadCommits)
</script>
