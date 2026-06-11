<template>
  <section>
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
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchProjects } from '../api/projects'
import { fetchRequirements } from '../api/requirements'
import { fetchTask } from '../api/tasks'
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
    const [taskRes, projectRes, requirementRes, userRes] = await Promise.all([
      fetchTask(taskId.value),
      fetchProjects(),
      fetchRequirements(),
      fetchUsers()
    ])
    task.value = taskRes.data
    projects.value = projectRes.data
    requirements.value = requirementRes.data
    users.value = userRes.data
  } catch {
    ElMessage.error('任务详情加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
