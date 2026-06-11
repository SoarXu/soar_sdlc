<template>
  <section class="requirement-detail-page">
    <div class="detail-titlebar">
      <el-button @click="goBackToProjectTasks">返回</el-button>
      <el-tag effect="plain">#{{ task.id }}</el-tag>
      <h1>{{ task.title || '任务详情' }}</h1>
      <router-link v-if="task.project_id" class="detail-link" :to="`/projects/${task.project_id}`">进入项目</router-link>
    </div>

    <el-card v-loading="loading" shadow="never" class="detail-panel">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="所属项目">{{ labelById(projects, task.project_id) }}</el-descriptions-item>
        <el-descriptions-item label="关联需求">
          <router-link v-if="task.requirement_id" class="table-link" :to="`/requirements/${task.requirement_id}`">{{ labelById(requirements, task.requirement_id, 'title') }}</router-link>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="负责人">{{ userLabel(users, task.owner_id) }}</el-descriptions-item>
        <el-descriptions-item label="优先级">{{ task.priority || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ task.status || '-' }}</el-descriptions-item>
        <el-descriptions-item label="任务类型">{{ task.task_type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="预计工时">{{ task.estimated_hours ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="实际工时">{{ task.actual_hours ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="截止日期">{{ task.due_date || '-' }}</el-descriptions-item>
      </el-descriptions>

      <div class="detail-sections">
        <section class="detail-section">
          <h2>任务描述</h2>
          <div class="rich-text">{{ task.description || '-' }}</div>
        </section>
        <section class="detail-section">
          <h2>来源快照</h2>
          <div class="rich-text">{{ task.source_requirement_review_status || '-' }}</div>
        </section>
      </div>
    </el-card>

    <el-card shadow="never" class="detail-panel requirement-history-card">
      <template #header>历史记录</template>
      <div class="project-history requirement-history">
        <el-empty v-if="!taskHistory.length" description="暂无历史记录" />
        <div v-else class="project-history-list">
          <div v-for="(item, index) in taskHistory" :key="item.key" class="project-history-entry">
            <div class="project-history-line">
              <span class="project-history-index">{{ index + 1 }}</span>
              <span>{{ formatDateTime(item.time) }}，由 {{ item.actor }} {{ item.actionLabel }}。</span>
              <button
                v-if="item.type === 'audit'"
                class="project-history-toggle"
                type="button"
                @click="toggleHistory(item.key)"
              >
                {{ expandedHistory[item.key] ? '-' : '+' }}
              </button>
            </div>
            <div v-if="item.type === 'audit' && expandedHistory[item.key]" class="project-history-detail">
              <p v-for="change in item.changes" :key="change.field">
                修改了 <strong>{{ taskFieldLabel(change.field) }}</strong>，旧值为 "{{ displayHistoryValue(change.oldValue) }}"，新值为 "{{ displayHistoryValue(change.newValue) }}"。
              </p>
            </div>
            <div v-if="item.type === 'status'" class="project-history-detail">
              <div class="status-history-meta">
                {{ taskStatusLabel(item.fromStatus) }} → {{ taskStatusLabel(item.toStatus) }}
                <template v-if="item.reason"> · 原因：{{ item.reason }}</template>
              </div>
              <p v-if="item.remark">{{ item.remark }}</p>
            </div>
          </div>
        </div>
      </div>
    </el-card>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchProjects } from '../api/projects'
import { fetchRequirements } from '../api/requirements'
import { fetchTask, fetchTaskAuditLogs, fetchTaskStatusOperations } from '../api/tasks'
import { fetchUsers } from '../api/users'
import { labelById, userLabel } from '../utils/referenceLabels'

const route = useRoute()
const router = useRouter()
const taskId = computed(() => Number(route.params.id))
const loading = ref(false)
const task = ref({})
const projects = ref([])
const requirements = ref([])
const users = ref([])
const statusOperations = ref([])
const auditLogs = ref([])
const expandedHistory = reactive({})
const taskStatusOptions = [
  { label: '待办', value: 'todo' },
  { label: '进行中', value: 'doing' },
  { label: '完成', value: 'done' },
  { label: '关闭', value: 'closed' }
]
const taskHistory = computed(() => {
  const statusItems = statusOperations.value.map((item) => ({
    key: `status-${item.id}`,
    type: 'status',
    time: item.effective_time || item.create_time,
    actor: item.actor_name || '系统',
    actionLabel: operationActionLabel(item.action),
    fromStatus: item.from_status,
    toStatus: item.to_status,
    reason: item.reason,
    remark: item.remark
  }))
  const auditItems = auditLogs.value.map((item) => ({
    key: `audit-${item.id}`,
    type: 'audit',
    time: item.create_time,
    actor: '系统',
    actionLabel: '编辑',
    changes: Object.keys(item.after_data || {}).map((field) => ({
      field,
      oldValue: item.before_data?.[field],
      newValue: item.after_data?.[field]
    }))
  }))
  return [...statusItems, ...auditItems].sort((a, b) => new Date(a.time) - new Date(b.time))
})

function optionLabel(options, value) { return options.find((option) => option.value === value)?.label || value || '-' }
function taskStatusLabel(value) { return optionLabel(taskStatusOptions, value) }
function operationActionLabel(value) { return optionLabel([{ label: '激活', value: 'activate' }, { label: '关闭', value: 'close' }], value) }
function toggleHistory(key) { expandedHistory[key] = !expandedHistory[key] }
function formatDateTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-' }
function displayHistoryValue(value) { return value === null || value === undefined || value === '' ? '-' : value }
function taskFieldLabel(field) {
  return optionLabel([
    { label: '所属项目', value: 'project_id' },
    { label: '来源项目', value: 'source_project_id' },
    { label: '关联需求', value: 'requirement_id' },
    { label: '任务标题', value: 'title' },
    { label: '任务类型', value: 'task_type' },
    { label: '优先级', value: 'priority' },
    { label: '负责人', value: 'owner_id' },
    { label: '预计工时', value: 'estimated_hours' },
    { label: '实际工时', value: 'actual_hours' },
    { label: '截止日期', value: 'due_date' },
    { label: '状态', value: 'status' },
    { label: '描述', value: 'description' }
  ], field)
}

function goBackToProjectTasks() {
  if (task.value.project_id) {
    router.push({ name: 'project-detail', params: { id: task.value.project_id }, query: { tab: 'tasks' } })
  } else {
    router.push({ name: 'tasks' })
  }
}

async function loadData() {
  loading.value = true
  try {
    const [taskRes, projectRes, requirementRes, userRes, operationRes, auditRes] = await Promise.all([
      fetchTask(taskId.value),
      fetchProjects(),
      fetchRequirements(),
      fetchUsers(),
      fetchTaskStatusOperations(taskId.value),
      fetchTaskAuditLogs(taskId.value)
    ])
    task.value = taskRes.data
    projects.value = projectRes.data
    requirements.value = requirementRes.data
    users.value = userRes.data
    statusOperations.value = operationRes.data
    auditLogs.value = auditRes.data
  } catch {
    ElMessage.error('任务详情加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
