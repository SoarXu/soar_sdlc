<template>
  <section>
    <div class="detail-titlebar">
      <el-button @click="$router.back()">返回</el-button>
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
        <el-descriptions-item label="状态">{{ requirement.status || '-' }}</el-descriptions-item>
        <el-descriptions-item label="评审状态">{{ requirement.review_status || '-' }}</el-descriptions-item>
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
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchIterations } from '../api/iterations'
import { fetchProjects } from '../api/projects'
import { fetchRequirement } from '../api/requirements'
import { fetchTasks } from '../api/tasks'
import { fetchUsers } from '../api/users'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import { labelById, userLabel } from '../utils/referenceLabels'

const route = useRoute()
const requirementId = computed(() => Number(route.params.id))
const loading = ref(false)
const requirement = ref({})
const projects = ref([])
const iterations = ref([])
const users = ref([])
const tasks = ref([])
const relatedTasks = computed(() => tasks.value.filter((item) => item.requirement_id === requirementId.value))

async function loadData() {
  loading.value = true
  try {
    const [requirementRes, projectRes, iterationRes, userRes, taskRes] = await Promise.all([
      fetchRequirement(requirementId.value),
      fetchProjects(),
      fetchIterations(),
      fetchUsers(),
      fetchTasks()
    ])
    requirement.value = requirementRes.data
    projects.value = projectRes.data
    iterations.value = iterationRes.data
    users.value = userRes.data
    tasks.value = taskRes.data
  } catch {
    ElMessage.error('需求详情加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
