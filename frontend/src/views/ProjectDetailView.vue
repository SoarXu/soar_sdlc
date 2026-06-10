<template>
  <section>
    <div class="project-detail-head">
      <div>
        <el-button link type="primary" @click="$router.push('/projects')">返回项目列表</el-button>
        <h1>{{ project.name || '项目详情' }}</h1>
        <p>
          {{ labelById(programs, project.program_id) }} · {{ userLabel(users, project.owner_id) }} ·
          {{ project.start_date || '未设置开始' }} 至 {{ projectEndDateLabel }}
        </p>
      </div>
      <el-tag size="large">{{ projectStatusLabel(project.status) }}</el-tag>
    </div>

    <div class="project-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="project-tab-button"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <el-card v-loading="loading" shadow="never">
      <template v-if="activeTab === 'overview'">
        <div class="metrics project-detail-metrics">
          <el-card v-for="item in metrics" :key="item.key" shadow="never">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </el-card>
        </div>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="项目名称">{{ project.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="所属项目集">{{ labelById(programs, project.program_id) }}</el-descriptions-item>
          <el-descriptions-item label="负责人">{{ userLabel(users, project.owner_id) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ projectStatusLabel(project.status) }}</el-descriptions-item>
          <el-descriptions-item label="开始日期">{{ project.start_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="结束日期">{{ projectEndDateLabel }}</el-descriptions-item>
          <el-descriptions-item label="描述" :span="2">{{ project.description || '-' }}</el-descriptions-item>
        </el-descriptions>
      </template>

      <template v-else>
        <div class="project-tab-placeholder">
          <h2>{{ activeTabLabel }}</h2>
          <p>当前页签将承载本项目下的{{ activeTabLabel }}数据，新增和编辑时自动带入当前项目。</p>
        </div>
      </template>
    </el-card>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchPrograms } from '../api/programs'
import { fetchProject } from '../api/projects'
import { fetchUsers } from '../api/users'
import { labelById, userLabel } from '../utils/referenceLabels'

const route = useRoute()
const loading = ref(false)
const activeTab = ref('overview')
const project = ref({})
const programs = ref([])
const users = ref([])

const tabs = [
  { key: 'overview', label: '概览' },
  { key: 'iterations', label: '迭代' },
  { key: 'requirements', label: '需求' },
  { key: 'tasks', label: '任务' },
  { key: 'tests', label: '测试' },
  { key: 'bugs', label: 'Bug' },
  { key: 'members', label: '成员' },
  { key: 'settings', label: '配置' }
]

const projectStatusOptions = [
  { label: '规划中', value: 'planning' },
  { label: '进行中', value: 'active' },
  { label: '已暂停', value: 'paused' },
  { label: '已关闭', value: 'closed' }
]

const activeTabLabel = computed(() => tabs.find((tab) => tab.key === activeTab.value)?.label || '')
const projectEndDateLabel = computed(() => {
  if (project.value.is_long_term) return '长期'
  return project.value.end_date || '未设置结束'
})
const metrics = computed(() => [
  { key: 'iterations', label: '迭代', value: '-' },
  { key: 'requirements', label: '需求', value: '-' },
  { key: 'tasks', label: '任务', value: '-' },
  { key: 'tests', label: '测试', value: '-' },
  { key: 'bugs', label: 'Bug', value: '-' }
])

function projectStatusLabel(value) {
  return projectStatusOptions.find((option) => option.value === value)?.label || value || '-'
}

async function loadData() {
  loading.value = true
  try {
    const [projectRes, programRes, userRes] = await Promise.all([
      fetchProject(route.params.id),
      fetchPrograms(),
      fetchUsers()
    ])
    project.value = projectRes.data
    programs.value = programRes.data
    users.value = userRes.data
  } catch {
    ElMessage.error('项目详情加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
