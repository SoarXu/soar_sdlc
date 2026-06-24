<template>
  <section class="requirement-detail-page">
    <div class="detail-titlebar">
      <el-button @click="goBack">返回</el-button>
      <el-tag effect="plain">#{{ bug.id }}</el-tag>
      <h1>{{ bug.title || 'Bug 详情' }}</h1>
      <router-link v-if="bug.project_id" class="detail-link" :to="`/projects/${bug.project_id}?tab=bugs`">进入项目</router-link>
    </div>

    <el-card v-loading="loading" shadow="never" class="detail-panel">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="所属项目">{{ labelById(projects, bug.project_id) }}</el-descriptions-item>
        <el-descriptions-item label="关联需求">
          <router-link v-if="bug.requirement_id" class="table-link" :to="`/requirements/${bug.requirement_id}`">{{ labelById(requirements, bug.requirement_id, 'title') }}</router-link>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="来源用例">
          <router-link v-if="bug.test_case_id" class="table-link" :to="{ name: 'test-case-detail', params: { id: bug.test_case_id } }">{{ labelById(testCases, bug.test_case_id, 'title') }}</router-link>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="负责人">{{ userLabel(users, bug.owner_id) }}</el-descriptions-item>
        <el-descriptions-item label="提出人">{{ userLabel(users, bug.reporter_id) }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ bugStatusLabel(bug.status) }}</el-descriptions-item>
        <el-descriptions-item label="严重程度"><RequirementPriorityBadge :value="bug.severity" /></el-descriptions-item>
        <el-descriptions-item label="优先级"><RequirementPriorityBadge :value="bug.priority" /></el-descriptions-item>
        <el-descriptions-item label="解决方案">{{ resolutionLabel(bug.resolution) }}</el-descriptions-item>
        <el-descriptions-item label="解决时间">{{ formatDateTime(bug.resolve_time) }}</el-descriptions-item>
        <el-descriptions-item label="验证结果">{{ bug.verify_result || '-' }}</el-descriptions-item>
        <el-descriptions-item label="重新打开次数">{{ bug.reopen_count ?? 0 }}</el-descriptions-item>
      </el-descriptions>

      <div class="detail-sections">
        <section class="detail-section">
          <h2>重现步骤</h2>
          <div class="rich-text" v-html="bug.reproduce_steps || '-'"></div>
        </section>
        <section class="detail-section">
          <h2>期望结果</h2>
          <div class="rich-text">{{ bug.expected_result || '-' }}</div>
        </section>
        <section class="detail-section">
          <h2>实际结果</h2>
          <div class="rich-text">{{ bug.actual_result || '-' }}</div>
        </section>
      </div>
    </el-card>

        <CommitRecordsPanel object-type="bug" :object-id="bugId" />

<el-card shadow="never" class="detail-panel requirement-history-card">
      <template #header>历史记录</template>
      <div class="project-history requirement-history">
        <el-empty v-if="!history.length" description="暂无历史记录" />
        <div v-else class="project-history-list">
          <div v-for="(item, index) in history" :key="item.id" class="project-history-entry">
            <div class="project-history-line">
              <span class="project-history-index">{{ index + 1 }}</span>
              <span>{{ formatDateTime(item.effective_time || item.create_time) }}，由 {{ item.actor_name || '系统' }} {{ actionLabel(item.action) }}。</span>
            </div>
            <div class="project-history-detail">
              <div class="status-history-meta">
                {{ bugStatusLabel(item.from_status) }} -> {{ bugStatusLabel(item.to_status) }}
                <template v-if="item.reason"> · {{ item.reason }}</template>
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
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchBug, fetchBugStatusOperations } from '../api/bugs'
import { fetchProjects } from '../api/projects'
import { fetchRequirements } from '../api/requirements'
import { fetchTestCases } from '../api/testCases'
import { fetchUsers } from '../api/users'
import CommitRecordsPanel from '../components/CommitRecordsPanel.vue'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import { labelById, userLabel } from '../utils/referenceLabels'

const route = useRoute()
const router = useRouter()
const bugId = computed(() => Number(route.params.id))
const loading = ref(false)
const bug = ref({})
const history = ref([])
const projects = ref([])
const requirements = ref([])
const testCases = ref([])
const users = ref([])

const bugStatusOptions = [
  { label: '待确认', value: 'open' },
  { label: '修复中', value: 'fixing' },
  { label: '已解决', value: 'resolved' },
  { label: '待验证', value: 'verifying' },
  { label: '已关闭', value: 'closed' },
  { label: '重新打开', value: 'reopened' },
  { label: '已挂起', value: 'suspended' }
]
const resolutionOptions = ['设计如此', '重复Bug', '外部原因', '已解决', '无法重现', '延期处理', '不予解决']
const actionOptions = [
  { label: '确认', value: 'confirm' },
  { label: '开始修复', value: 'start_fixing' },
  { label: '解决', value: 'resolve' },
  { label: '激活', value: 'activate' },
  { label: '挂起', value: 'suspend' },
  { label: '关闭', value: 'close' }
]

function optionLabel(options, value) {
  const option = options.find((item) => item.value === value)
  return option?.label || value || '-'
}
function bugStatusLabel(value) { return optionLabel(bugStatusOptions, value) }
function actionLabel(value) { return optionLabel(actionOptions, value) }
function resolutionLabel(value) { return resolutionOptions.includes(value) ? value : value || '-' }
function formatDateTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-' }
function goBack() {
  if (route.query.from === 'dashboard') {
    router.push({ name: 'dashboard' })
    return
  }
  if (route.query.from === 'project' && bug.value.project_id) {
    router.push({ name: 'project-detail', params: { id: bug.value.project_id }, query: { tab: 'bugs' } })
    return
  }
  if (route.query.from === 'iteration' && route.query.iterationId) {
    router.push({ name: 'iteration-detail', params: { id: route.query.iterationId }, query: { tab: route.query.tab || 'bugs' } })
    return
  }
  router.push({ name: 'bugs' })
}

async function loadData() {
  loading.value = true
  try {
    const [bugRes, historyRes, projectRes, requirementRes, testCaseRes, userRes] = await Promise.all([
      fetchBug(bugId.value),
      fetchBugStatusOperations(bugId.value),
      fetchProjects(),
      fetchRequirements(),
      fetchTestCases(),
      fetchUsers()
    ])
    bug.value = bugRes.data
    history.value = historyRes.data
    projects.value = projectRes.data
    requirements.value = requirementRes.data
    testCases.value = testCaseRes.data
    users.value = userRes.data
  } catch {
    ElMessage.error('Bug 详情加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
