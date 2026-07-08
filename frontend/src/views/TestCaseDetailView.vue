<template>
  <section class="requirement-detail-page">
    <div class="detail-titlebar">
      <el-button @click="goBack">返回</el-button>
      <el-tag effect="plain">#{{ testCase.id }}</el-tag>
      <h1>{{ testCase.title || '测试用例详情' }}</h1>
      <router-link v-if="testCase.project_id" class="detail-link" :to="`/projects/${testCase.project_id}?tab=tests`">进入项目</router-link>
      <el-button v-if="!editing" type="primary" @click="startEdit">编辑</el-button>
      <template v-else>
        <el-button @click="cancelEdit">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveTestCase">保存</el-button>
      </template>
    </div>

    <el-card v-loading="loading" shadow="never" class="detail-panel">
      <el-form v-if="editing" label-position="top">
        <el-form-item label="用例标题" required><el-input v-model="caseForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="所属项目"><el-select v-model="caseForm.project_id" clearable filterable><el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" /></el-select></el-form-item>
          <el-form-item label="关联需求"><el-select v-model="caseForm.requirement_id" clearable filterable><el-option v-for="requirement in requirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item>
          <el-form-item label="测试人"><el-select v-model="caseForm.default_tester_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="用例类型"><el-select v-model="caseForm.case_type"><el-option v-for="option in caseTypeOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
          <el-form-item label="适用范围"><el-select v-model="caseForm.test_scope"><el-option v-for="option in testScopeOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
        </div>
        <el-form-item label="前置条件"><el-input v-model="caseForm.precondition" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="用例步骤">
          <div class="case-steps-editor">
            <el-table :data="caseForm.steps_json" border>
              <el-table-column label="步骤" min-width="260"><template #default="{ row, $index }"><el-input v-model="row.step" :placeholder="`步骤 ${$index + 1}`" /></template></el-table-column>
              <el-table-column label="预期" min-width="260"><template #default="{ row }"><el-input v-model="row.expected" placeholder="预期结果" /></template></el-table-column>
              <el-table-column label="操作" width="90"><template #default="{ $index }"><el-button link type="danger" :disabled="caseForm.steps_json.length === 1" @click="removeCaseStep($index)">删除</el-button></template></el-table-column>
            </el-table>
            <el-button class="case-step-add" @click="addCaseStep">增加步骤</el-button>
          </div>
        </el-form-item>
        <el-form-item label="预期结果"><el-input v-model="caseForm.expected_result" type="textarea" :rows="3" /></el-form-item>
      </el-form>

      <template v-else>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="所属项目">{{ labelById(projects, testCase.project_id) }}</el-descriptions-item>
        <el-descriptions-item label="关联需求">
          <router-link v-if="linkedRequirement" class="table-link" :to="`/requirements/${linkedRequirement.id}`">{{ linkedRequirement.title }}</router-link>
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
      </template>
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
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchProjects } from '../api/projects'
import { fetchRequirements } from '../api/requirements'
import { fetchTestCase, fetchTestCaseExecutions, updateTestCase } from '../api/testCases'
import { fetchUsers } from '../api/users'
import { labelById, userLabel } from '../utils/referenceLabels'

const route = useRoute()
const router = useRouter()
const testCaseId = computed(() => Number(route.params.id))
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const testCase = ref({})
const executions = ref([])
const projects = ref([])
const requirements = ref([])
const users = ref([])
const caseSteps = computed(() => (Array.isArray(testCase.value.steps_json) && testCase.value.steps_json.length ? testCase.value.steps_json : []))
const linkedRequirement = computed(() => requirements.value.find((item) => item.id === testCase.value.requirement_id))
const caseForm = reactive({ project_id: null, requirement_id: null, title: '', case_type: 'functional', test_scope: 'functional_test', default_tester_id: null, precondition: '', steps_json: [{ step: '', expected: '' }], expected_result: '' })

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
  if (route.query.from === 'dashboard') {
    router.push({ name: 'dashboard' })
    return
  }
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

function normalizeCaseSteps(value) {
  return Array.isArray(value) && value.length ? value.map((item) => ({ step: item.step || '', expected: item.expected || '' })) : [{ step: '', expected: '' }]
}
function addCaseStep() { caseForm.steps_json.push({ step: '', expected: '' }) }
function removeCaseStep(index) { if (caseForm.steps_json.length > 1) caseForm.steps_json.splice(index, 1) }
function cleanCaseSteps() { return caseForm.steps_json.filter((item) => item.step.trim() || item.expected.trim()) }
function fillCaseForm() {
  Object.assign(caseForm, {
    project_id: testCase.value.project_id || null,
    requirement_id: testCase.value.requirement_id || null,
    title: testCase.value.title || '',
    case_type: testCase.value.case_type || 'functional',
    test_scope: testCase.value.test_scope || 'functional_test',
    default_tester_id: testCase.value.default_tester_id || null,
    precondition: testCase.value.precondition || '',
    steps_json: normalizeCaseSteps(testCase.value.steps_json),
    expected_result: testCase.value.expected_result || ''
  })
}
function startEdit() {
  fillCaseForm()
  editing.value = true
}
function cancelEdit() {
  editing.value = false
  fillCaseForm()
}
async function saveTestCase() {
  if (!caseForm.title.trim()) return ElMessage.warning('请填写用例标题')
  saving.value = true
  try {
    await updateTestCase(testCaseId.value, {
      ...caseForm,
      project_id: caseForm.project_id || null,
      requirement_id: caseForm.requirement_id || null,
      default_tester_id: caseForm.default_tester_id || null,
      steps_json: cleanCaseSteps()
    })
    editing.value = false
    await loadData()
    ElMessage.success('用例已保存')
  } finally {
    saving.value = false
  }
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
    fillCaseForm()
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
