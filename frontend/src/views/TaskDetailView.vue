<template>
  <section class="requirement-detail-page">
    <div class="detail-titlebar">
      <el-button @click="goBackToProjectTasks">返回</el-button>
      <el-tag effect="plain">#{{ task.id }}</el-tag>
      <h1>{{ task.title || '任务详情' }}</h1>
      <router-link v-if="task.project_id" class="detail-link" :to="`/projects/${task.project_id}`">进入项目</router-link>
      <WorkflowActionButtons
        v-if="!editing && task.id"
        object-type="task"
        :object-id="taskId"
        mode="detail"
        :users="users"
        @executed="loadData"
      />
      <el-button v-if="!editing" type="primary" @click="startEdit">编辑</el-button>
      <template v-else>
        <el-button @click="cancelEdit">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveTask">保存</el-button>
      </template>
    </div>

    <el-card v-loading="loading" shadow="never" class="detail-panel">
      <el-form v-if="editing" label-position="top">
        <el-form-item label="任务标题" required><el-input v-model="taskForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="关联需求"><el-select v-model="taskForm.requirement_id" clearable filterable><el-option v-for="requirement in requirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item>
          <el-form-item label="负责人"><el-select v-model="taskForm.owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="优先级"><el-select v-model="taskForm.priority"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item>
          <el-form-item label="截止日期"><el-date-picker v-model="taskForm.due_date" value-format="YYYY-MM-DD" type="date" /></el-form-item>
        </div>
        <el-form-item label="描述"><el-input v-model="taskForm.description" type="textarea" :rows="4" /></el-form-item>
      </el-form>

      <template v-else>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="所属项目">{{ labelById(projects, task.project_id) }}</el-descriptions-item>
        <el-descriptions-item label="关联需求">
          <router-link v-if="task.requirement_id" class="table-link" :to="`/requirements/${task.requirement_id}`">{{ labelById(requirements, task.requirement_id, 'title') }}</router-link>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="负责人">{{ userLabel(users, task.owner_id) }}</el-descriptions-item>
        <el-descriptions-item label="优先级">{{ task.priority || '-' }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ task.status || '-' }}</el-descriptions-item>
        <el-descriptions-item label="截止日期">{{ task.due_date || '-' }}</el-descriptions-item>
      </el-descriptions>

      <div class="detail-sections">
        <section class="detail-section">
          <h2>任务描述</h2>
          <div class="rich-text">{{ task.description || '-' }}</div>
        </section>
      </div>
      </template>
    </el-card>

        <CommitRecordsPanel object-type="task" :object-id="taskId" />

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
                修改了 <strong>{{ taskFieldLabel(change.field) }}</strong>，旧值为 "{{ displayHistoryValue(change.field, change.oldValue) }}"，新值为 "{{ displayHistoryValue(change.field, change.newValue) }}"。
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
import { fetchTask, fetchTaskAuditLogs, fetchTaskStatusOperations, updateTask } from '../api/tasks'
import { fetchUsers } from '../api/users'
import CommitRecordsPanel from '../components/CommitRecordsPanel.vue'
import WorkflowActionButtons from '../components/WorkflowActionButtons.vue'
import { labelById, userLabel } from '../utils/referenceLabels'
import { formatAuditValue } from '../utils/auditHistoryLabels'

const route = useRoute()
const router = useRouter()
const taskId = computed(() => Number(route.params.id))
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const task = ref({})
const projects = ref([])
const requirements = ref([])
const users = ref([])
const statusOperations = ref([])
const auditLogs = ref([])
const expandedHistory = reactive({})
const taskForm = reactive({ requirement_id: null, title: '', priority: 'medium', owner_id: null, due_date: null, description: '' })
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
    actor: item.actor_name || '系统',
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
function displayHistoryValue(field, value) {
  return formatAuditValue(field, value, {
    users: users.value,
    projects: projects.value,
    requirements: requirements.value
  })
}
function taskFieldLabel(field) {
  return optionLabel([
    { label: '所属项目', value: 'project_id' },
    { label: '来源项目', value: 'source_project_id' },
    { label: '关联需求', value: 'requirement_id' },
    { label: '任务标题', value: 'title' },
    { label: '优先级', value: 'priority' },
    { label: '负责人', value: 'owner_id' },
    { label: '截止日期', value: 'due_date' },
    { label: '状态', value: 'status' },
    { label: '描述', value: 'description' }
  ], field)
}

function goBackToProjectTasks() {
  if (route.query.from === 'dashboard') {
    router.push({ name: 'dashboard' })
    return
  }
  if (route.query.from === 'iteration' && route.query.iterationId) {
    router.push({ name: 'iteration-detail', params: { id: route.query.iterationId }, query: { tab: route.query.tab || 'tasks' } })
    return
  }
  if (task.value.project_id) {
    router.push({ name: 'project-detail', params: { id: task.value.project_id }, query: { tab: 'tasks' } })
  } else {
    router.push({ name: 'tasks' })
  }
}

function fillTaskForm() {
  Object.assign(taskForm, {
    requirement_id: task.value.requirement_id || null,
    title: task.value.title || '',
    priority: task.value.priority || 'medium',
    owner_id: task.value.owner_id || null,
    due_date: task.value.due_date || null,
    description: task.value.description || ''
  })
}

function startEdit() {
  fillTaskForm()
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  fillTaskForm()
}

async function saveTask() {
  if (!taskForm.title.trim()) return ElMessage.warning('请填写任务标题')
  saving.value = true
  try {
    await updateTask(taskId.value, {
      ...taskForm,
      project_id: task.value.project_id,
      requirement_id: taskForm.requirement_id || null,
      owner_id: taskForm.owner_id || null
    })
    editing.value = false
    await loadData()
    ElMessage.success('任务已保存')
  } finally {
    saving.value = false
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
    fillTaskForm()
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
