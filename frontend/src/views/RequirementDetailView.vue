<template>
  <section class="requirement-detail-page">
    <div class="detail-titlebar">
      <el-button @click="goBackToProjectRequirements">返回</el-button>
      <el-tag effect="plain">#{{ requirement.id }}</el-tag>
      <h1>{{ requirement.title || '需求详情' }}</h1>
      <router-link v-if="requirement.project_id" class="detail-link" :to="`/projects/${requirement.project_id}`">进入项目</router-link>
      <el-button v-if="!editing" type="primary" @click="startEdit">编辑</el-button>
      <template v-else>
        <el-button @click="cancelEdit">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveRequirement">保存</el-button>
      </template>
    </div>

    <el-card v-loading="loading" shadow="never" class="detail-panel">
      <el-form v-if="editing" label-position="top">
        <el-form-item label="需求标题" required><el-input v-model="requirementForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="迭代"><el-select v-model="requirementForm.iteration_id" clearable filterable><el-option v-for="iteration in iterations" :key="iteration.id" :label="iteration.name" :value="iteration.id" /></el-select></el-form-item>
          <el-form-item label="负责人"><el-select v-model="requirementForm.owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="提出人"><el-select v-model="requirementForm.proposer_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="类型"><el-select v-model="requirementForm.requirement_type"><el-option v-for="option in requirementTypeOptions" :key="option" :label="option" :value="option" /></el-select></el-form-item>
          <el-form-item label="优先级"><el-select v-model="requirementForm.priority"><el-option v-for="option in requirementPriorityOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item>
          <el-form-item label="评审状态"><el-select v-model="requirementForm.review_status"><el-option v-for="option in reviewStatusOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
        </div>
        <el-form-item label="需求描述"><el-input v-model="requirementForm.description" type="textarea" :rows="4" /></el-form-item>
        <el-form-item label="验收标准"><el-input v-model="requirementForm.acceptance_criteria" type="textarea" :rows="4" /></el-form-item>
      </el-form>

      <template v-else>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="所属项目">{{ labelById(projects, requirement.project_id) }}</el-descriptions-item>
        <el-descriptions-item label="迭代">{{ labelById(iterations, requirement.iteration_id) }}</el-descriptions-item>
        <el-descriptions-item label="负责人">{{ userLabel(users, requirement.owner_id) }}</el-descriptions-item>
        <el-descriptions-item label="提出人">{{ userLabel(users, requirement.proposer_id) }}</el-descriptions-item>
        <el-descriptions-item label="优先级"><RequirementPriorityBadge :value="requirement.priority" /></el-descriptions-item>
        <el-descriptions-item label="状态">{{ requirementStatusLabel(requirement.status) }}</el-descriptions-item>
        <el-descriptions-item label="评审状态">{{ reviewStatusLabel(requirement.review_status) }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ requirement.requirement_type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="来源项目">{{ labelById(projects, requirement.source_project_id) }}</el-descriptions-item>
      </el-descriptions>

      <div class="detail-sections">
        <section class="detail-section">
          <h2>需求描述</h2>
          <div class="rich-text">{{ requirement.description || '-' }}</div>
        </section>
        <section class="detail-section">
          <h2>验收标准</h2>
          <div class="rich-text">{{ requirement.acceptance_criteria || '-' }}</div>
        </section>
      </div>
      </template>
    </el-card>

    <el-card shadow="never" class="detail-panel">
      <template #header>关联任务</template>
      <el-table :data="relatedTasks" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="任务标题" min-width="220">
          <template #default="{ row }"><router-link class="table-link" :to="`/tasks/${row.id}`">{{ row.title }}</router-link></template>
        </el-table-column>
        <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column prop="status" label="状态" width="120" />
      </el-table>
    </el-card>

        <CommitRecordsPanel object-type="requirement" :object-id="requirementId" />

<el-card shadow="never" class="detail-panel requirement-history-card">
      <template #header>历史记录</template>
      <div class="project-history requirement-history">
        <el-empty v-if="!requirementHistory.length" description="暂无历史记录" />
        <div v-else class="project-history-list">
          <div v-for="(item, index) in requirementHistory" :key="item.key" class="project-history-entry">
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
                修改了 <strong>{{ requirementFieldLabel(change.field) }}</strong>，旧值为 "{{ displayHistoryValue(change.field, change.oldValue) }}"，新值为 "{{ displayHistoryValue(change.field, change.newValue) }}"。
              </p>
            </div>
            <div v-if="item.type === 'status'" class="project-history-detail">
              <div class="status-history-meta">
                {{ requirementStatusLabel(item.fromStatus) }} → {{ requirementStatusLabel(item.toStatus) }}
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

import { fetchIterations } from '../api/iterations'
import { fetchProjects } from '../api/projects'
import { fetchRequirement, fetchRequirementAuditLogs, fetchRequirementStatusOperations, updateRequirement } from '../api/requirements'
import { fetchTasks } from '../api/tasks'
import { fetchUsers } from '../api/users'
import CommitRecordsPanel from '../components/CommitRecordsPanel.vue'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import { labelById, userLabel } from '../utils/referenceLabels'
import { formatAuditValue } from '../utils/auditHistoryLabels'

const route = useRoute()
const router = useRouter()
const requirementId = computed(() => Number(route.params.id))
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const requirement = ref({})
const projects = ref([])
const iterations = ref([])
const users = ref([])
const tasks = ref([])
const statusOperations = ref([])
const auditLogs = ref([])
const expandedHistory = reactive({})
const requirementForm = reactive({ iteration_id: null, title: '', requirement_type: '功能', priority: '3', owner_id: null, proposer_id: null, review_status: 'not_required', description: '', acceptance_criteria: '' })
const relatedTasks = computed(() => tasks.value.filter((item) => item.requirement_id === requirementId.value))
const requirementHistory = computed(() => {
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
const requirementStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '激活', value: 'active' },
  { label: '完成', value: 'done' },
  { label: '关闭', value: 'closed' }
]
const operationActionOptions = [
  { label: '激活', value: 'activate' },
  { label: '关闭', value: 'close' }
]
const reviewStatusOptions = [
  { label: '无需评审', value: 'not_required' },
  { label: '待评审', value: 'pending' },
  { label: '已通过', value: 'approved' },
  { label: '已拒绝', value: 'rejected' }
]
const requirementTypeOptions = ['功能', '接口', '性能', '安全', '体验', '改进', '其他']
const requirementPriorityOptions = [
  { label: '1级', value: '1' },
  { label: '2级', value: '2' },
  { label: '3级', value: '3' },
  { label: '4级', value: '4' },
  { label: '5级', value: '5' }
]

function optionLabel(options, value) { return options.find((option) => option.value === value)?.label || value || '-' }
function requirementStatusLabel(value) { return optionLabel(requirementStatusOptions, value) }
function reviewStatusLabel(value) { return optionLabel(reviewStatusOptions, value) }
function operationActionLabel(value) { return optionLabel(operationActionOptions, value) }
function formatDateTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}
function toggleHistory(key) { expandedHistory[key] = !expandedHistory[key] }
function displayHistoryValue(field, value) {
  return formatAuditValue(field, value, {
    users: users.value,
    projects: projects.value,
    iterations: iterations.value
  })
}
function requirementFieldLabel(field) {
  return optionLabel([
    { label: '所属项目', value: 'project_id' },
    { label: '来源项目', value: 'source_project_id' },
    { label: '迭代', value: 'iteration_id' },
    { label: '需求标题', value: 'title' },
    { label: '需求类型', value: 'requirement_type' },
    { label: '优先级', value: 'priority' },
    { label: '负责人', value: 'owner_id' },
    { label: '提出人', value: 'proposer_id' },
    { label: '评审状态', value: 'review_status' },
    { label: '需求描述', value: 'description' },
    { label: '验收标准', value: 'acceptance_criteria' },
    { label: '是否评审通过', value: 'source_reviewed' }
  ], field)
}
function goBackToProjectRequirements() {
  if (route.query.from === 'dashboard') {
    router.push({ name: 'dashboard' })
    return
  }
  if (route.query.from === 'iteration' && route.query.iterationId) {
    router.push({ name: 'iteration-detail', params: { id: route.query.iterationId }, query: { tab: route.query.tab || 'requirements' } })
    return
  }
  if (requirement.value.project_id) {
    router.push({ name: 'project-detail', params: { id: requirement.value.project_id }, query: { tab: 'requirements' } })
  } else {
    router.push({ name: 'requirements' })
  }
}

function fillRequirementForm() {
  Object.assign(requirementForm, {
    iteration_id: requirement.value.iteration_id || null,
    title: requirement.value.title || '',
    requirement_type: requirement.value.requirement_type || '功能',
    priority: String(requirement.value.priority || '3'),
    owner_id: requirement.value.owner_id || null,
    proposer_id: requirement.value.proposer_id || null,
    review_status: requirement.value.review_status || 'not_required',
    description: requirement.value.description || '',
    acceptance_criteria: requirement.value.acceptance_criteria || ''
  })
}

function startEdit() {
  fillRequirementForm()
  editing.value = true
}

function cancelEdit() {
  editing.value = false
  fillRequirementForm()
}

async function saveRequirement() {
  if (!requirementForm.title.trim()) return ElMessage.warning('请填写需求标题')
  saving.value = true
  try {
    await updateRequirement(requirementId.value, {
      ...requirementForm,
      project_id: requirement.value.project_id,
      iteration_id: requirementForm.iteration_id || null,
      owner_id: requirementForm.owner_id || null,
      proposer_id: requirementForm.proposer_id || null
    })
    editing.value = false
    await loadData()
    ElMessage.success('需求已保存')
  } finally {
    saving.value = false
  }
}

async function loadData() {
  loading.value = true
  try {
    const [requirementRes, projectRes, iterationRes, userRes, taskRes, operationRes, auditRes] = await Promise.all([
      fetchRequirement(requirementId.value),
      fetchProjects(),
      fetchIterations(),
      fetchUsers(),
      fetchTasks(),
      fetchRequirementStatusOperations(requirementId.value),
      fetchRequirementAuditLogs(requirementId.value)
    ])
    requirement.value = requirementRes.data
    fillRequirementForm()
    projects.value = projectRes.data
    iterations.value = iterationRes.data
    users.value = userRes.data
    tasks.value = taskRes.data
    statusOperations.value = operationRes.data
    auditLogs.value = auditRes.data
  } catch {
    ElMessage.error('需求详情加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
