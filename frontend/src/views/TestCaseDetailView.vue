<template>
  <section class="requirement-detail-page">
    <div class="detail-titlebar">
      <el-button @click="goBack">返回</el-button>
      <el-tag effect="plain">#{{ testCase.id }}</el-tag>
      <h1>{{ testCase.title || '测试用例详情' }}</h1>
      <router-link v-if="testCase.project_id" class="detail-link" :to="`/projects/${testCase.project_id}?tab=tests`">进入项目</router-link>
    </div>

    <el-card v-loading="loading" shadow="never" class="detail-panel">
      <el-descriptions :column="3" border>
        <el-descriptions-item label="所属项目">{{ labelById(projects, testCase.project_id) }}</el-descriptions-item>
        <el-descriptions-item label="关联需求">
          <router-link v-if="testCase.requirement_id" class="table-link" :to="`/requirements/${testCase.requirement_id}`">{{ labelById(requirements, testCase.requirement_id, 'title') }}</router-link>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="测试人">{{ userLabel(users, testCase.default_tester_id) }}</el-descriptions-item>
        <el-descriptions-item label="用例类型">{{ caseTypeLabel(testCase.case_type) }}</el-descriptions-item>
        <el-descriptions-item label="适用范围">{{ testScopeLabel(testCase.test_scope) }}</el-descriptions-item>
        <el-descriptions-item label="最近结果">{{ executionResultLabel(testCase.last_execute_result) }}</el-descriptions-item>
        <el-descriptions-item label="最近执行时间">{{ formatDateTime(testCase.last_execute_time) }}</el-descriptions-item>
      </el-descriptions>

      <div class="detail-sections">
        <section class="detail-section">
          <h2>前置条件</h2>
          <div class="rich-text">{{ testCase.precondition || '-' }}</div>
        </section>
        <section class="detail-section">
          <h2>预期结果</h2>
          <div class="rich-text">{{ testCase.expected_result || '-' }}</div>
        </section>
      </div>

      <el-table :data="caseSteps" border class="detail-table">
        <el-table-column label="步骤" min-width="260"><template #default="{ row, $index }">{{ row.step || `步骤 ${$index + 1}` }}</template></el-table-column>
        <el-table-column prop="expected" label="预期" min-width="260" />
      </el-table>
    </el-card>

    <el-card shadow="never" class="detail-panel requirement-history-card">
      <template #header>历史记录</template>
      <div class="project-history requirement-history">
        <el-empty v-if="!executions.length" description="暂无历史记录" />
        <div v-else class="project-history-list">
          <div v-for="(item, index) in executions" :key="item.id" class="project-history-entry">
            <div class="project-history-line">
              <span class="project-history-index">{{ index + 1 }}</span>
              <span>{{ formatDateTime(item.execute_time) }}，执行结果为 {{ executionResultLabel(item.result) }}。</span>
            </div>
            <div class="project-history-detail">
              <el-table :data="item.steps_result_json || []" border>
                <el-table-column prop="step" label="步骤" min-width="220" />
                <el-table-column prop="expected" label="预期" min-width="220" />
                <el-table-column label="测试结果" width="120"><template #default="{ row }">{{ executionResultLabel(row.result) }}</template></el-table-column>
                <el-table-column prop="actual" label="实际情况" min-width="220" />
              </el-table>
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

import { fetchProjects } from '../api/projects'
import { fetchRequirements } from '../api/requirements'
import { fetchTestCase, fetchTestCaseExecutions } from '../api/testCases'
import { fetchUsers } from '../api/users'
import { labelById, userLabel } from '../utils/referenceLabels'

const route = useRoute()
const router = useRouter()
const testCaseId = computed(() => Number(route.params.id))
const loading = ref(false)
const testCase = ref({})
const executions = ref([])
const projects = ref([])
const requirements = ref([])
const users = ref([])
const caseSteps = computed(() => (Array.isArray(testCase.value.steps_json) && testCase.value.steps_json.length ? testCase.value.steps_json : []))

const caseTypeOptions = [
  { label: '接口测试', value: 'api' },
  { label: '功能测试', value: 'functional' },
  { label: '安装部署', value: 'deploy' },
  { label: '配置相关', value: 'config' },
  { label: '性能测试', value: 'performance' },
  { label: '安全相关', value: 'security' },
  { label: '其他', value: 'other' }
]
const testScopeOptions = [
  { label: '单元测试环节', value: 'unit_test' },
  { label: '功能测试环节', value: 'functional_test' },
  { label: '集成测试环节', value: 'integration_test' },
  { label: '系统测试环节', value: 'system_test' },
  { label: '冒烟测试环节', value: 'smoke_test' },
  { label: '版本验证环节', value: 'release_verification' }
]
const executionResultOptions = [
  { label: '忽略', value: 'ignored' },
  { label: '通过', value: 'passed' },
  { label: '失败', value: 'failed' },
  { label: '阻塞', value: 'blocked' }
]

function optionLabel(options, value) { return options.find((option) => option.value === value)?.label || value || '-' }
function caseTypeLabel(value) { return optionLabel(caseTypeOptions, value) }
function testScopeLabel(value) { return optionLabel(testScopeOptions, value) }
function executionResultLabel(value) { return optionLabel(executionResultOptions, value) }
function formatDateTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-' }
function goBack() {
  if (route.query.from === 'iteration' && route.query.iterationId) {
    router.push({ name: 'iteration-detail', params: { id: route.query.iterationId }, query: { tab: route.query.tab || 'cases' } })
    return
  }
  if (route.query.from === 'project' && testCase.value.project_id) {
    router.push({ name: 'project-detail', params: { id: testCase.value.project_id }, query: { tab: 'tests' } })
    return
  }
  router.push({ name: 'tests' })
}

async function loadData() {
  loading.value = true
  try {
    const [caseRes, executionRes, projectRes, requirementRes, userRes] = await Promise.all([
      fetchTestCase(testCaseId.value),
      fetchTestCaseExecutions(testCaseId.value),
      fetchProjects(),
      fetchRequirements(),
      fetchUsers()
    ])
    testCase.value = caseRes.data
    executions.value = executionRes.data
    projects.value = projectRes.data
    requirements.value = requirementRes.data
    users.value = userRes.data
  } catch {
    ElMessage.error('测试用例详情加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
