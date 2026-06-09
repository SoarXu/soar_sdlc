<template>
  <section>
    <div class="page-head">
      <div>
        <h1>工作台</h1>
        <p>从后端接口读取项目集、项目、需求、任务和未关闭 Bug 的实时统计。</p>
      </div>
      <el-button :loading="loading" @click="loadSummary">刷新</el-button>
    </div>

    <div class="metrics">
      <el-card v-for="item in metrics" :key="item.key" shadow="never">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </el-card>
    </div>

    <el-card shadow="never">
      <template #header>数据来源</template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="接口">GET /api/v1/dashboard/summary</el-descriptions-item>
        <el-descriptions-item label="数据库">intellective_bio_sdlc</el-descriptions-item>
        <el-descriptions-item label="刷新时间">{{ refreshedAt || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ loading ? '加载中' : '已同步' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchDashboardSummary } from '../api/dashboard'

const loading = ref(false)
const summary = ref({
  programs: 0,
  projects: 0,
  requirements: 0,
  tasks: 0,
  open_bugs: 0
})
const refreshedAt = ref('')

const metrics = computed(() => [
  { key: 'programs', label: '项目集', value: summary.value.programs },
  { key: 'projects', label: '项目', value: summary.value.projects },
  { key: 'requirements', label: '需求', value: summary.value.requirements },
  { key: 'tasks', label: '任务', value: summary.value.tasks },
  { key: 'open_bugs', label: '未关闭 Bug', value: summary.value.open_bugs }
])

async function loadSummary() {
  loading.value = true
  try {
    const { data } = await fetchDashboardSummary()
    summary.value = data
    refreshedAt.value = new Date().toLocaleString()
  } catch (error) {
    ElMessage.error('工作台统计加载失败，请确认后端服务已启动')
  } finally {
    loading.value = false
  }
}

onMounted(loadSummary)
</script>
