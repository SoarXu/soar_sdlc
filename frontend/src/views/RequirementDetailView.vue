<template>
  <section>
    <div class="detail-titlebar">
      <el-button @click="goBackToProjectRequirements">返回</el-button>
      <el-tag effect="plain">#{{ requirement.id }}</el-tag>
      <h1>{{ requirement.title || '需求详情' }}</h1>
      <router-link v-if="requirement.project_id" class="detail-link" :to="`/projects/${requirement.project_id}`">进入项目</router-link>
    </div>

    <el-card v-loading="loading" shadow="never" class="detail-panel">
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

    <el-card shadow="never" class="detail-panel">
      <template #header>状态历史</template>
      <el-empty v-if="!statusOperations.length" description="暂无状态历史" />
      <el-timeline v-else class="status-history">
        <el-timeline-item
          v-for="operation in statusOperations"
          :key="operation.id"
          :timestamp="formatDateTime(operation.effective_time)"
          placement="top"
        >
          <div class="status-history-item">
            <div class="status-history-title">
              {{ operationActionLabel(operation.action) }}
              <span>{{ requirementStatusLabel(operation.from_status) }} → {{ requirementStatusLabel(operation.to_status) }}</span>
            </div>
            <div class="status-history-meta">
              操作人：{{ operation.actor_name || '系统' }}
              <template v-if="operation.reason"> · 原因：{{ operation.reason }}</template>
            </div>
            <p v-if="operation.remark">{{ operation.remark }}</p>
          </div>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchIterations } from '../api/iterations'
import { fetchProjects } from '../api/projects'
import { fetchRequirement, fetchRequirementStatusOperations } from '../api/requirements'
import { fetchTasks } from '../api/tasks'
import { fetchUsers } from '../api/users'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import { labelById, userLabel } from '../utils/referenceLabels'

const route = useRoute()
const router = useRouter()
const requirementId = computed(() => Number(route.params.id))
const loading = ref(false)
const requirement = ref({})
const projects = ref([])
const iterations = ref([])
const users = ref([])
const tasks = ref([])
const statusOperations = ref([])
const relatedTasks = computed(() => tasks.value.filter((item) => item.requirement_id === requirementId.value))
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

function optionLabel(options, value) { return options.find((option) => option.value === value)?.label || value || '-' }
function requirementStatusLabel(value) { return optionLabel(requirementStatusOptions, value) }
function reviewStatusLabel(value) { return optionLabel(reviewStatusOptions, value) }
function operationActionLabel(value) { return optionLabel(operationActionOptions, value) }
function formatDateTime(value) {
  if (!value) return ''
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}
function goBackToProjectRequirements() {
  if (requirement.value.project_id) {
    router.push({ name: 'project-detail', params: { id: requirement.value.project_id }, query: { tab: 'requirements' } })
  } else {
    router.push({ name: 'requirements' })
  }
}

async function loadData() {
  loading.value = true
  try {
    const [requirementRes, projectRes, iterationRes, userRes, taskRes, operationRes] = await Promise.all([
      fetchRequirement(requirementId.value),
      fetchProjects(),
      fetchIterations(),
      fetchUsers(),
      fetchTasks(),
      fetchRequirementStatusOperations(requirementId.value)
    ])
    requirement.value = requirementRes.data
    projects.value = projectRes.data
    iterations.value = iterationRes.data
    users.value = userRes.data
    tasks.value = taskRes.data
    statusOperations.value = operationRes.data
  } catch {
    ElMessage.error('需求详情加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
