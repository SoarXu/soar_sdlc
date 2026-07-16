<template>
  <section class="requirement-detail-page">
    <div class="detail-titlebar">
      <el-button @click="goBack">返回</el-button>
      <el-tag effect="plain">#{{ bug.id }}</el-tag>
      <h1>{{ bug.title || 'Bug 详情' }}</h1>
      <router-link v-if="bug.project_id" class="detail-link" :to="`/projects/${bug.project_id}?tab=bugs`">进入项目</router-link>
      <WatchToggleButton v-if="bug.id" object-type="bug" :object-id="bugId" />
      <WorkflowActionButtons
        v-if="!editing && bug.id"
        object-type="bug"
        :object-id="bugId"
        mode="detail"
        :users="users"
        @command="handleWorkflowCommand"
        @executed="loadData"
      />
      <template v-else>
        <el-button @click="cancelEdit">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveBug">保存</el-button>
      </template>
    </div>

    <el-card v-loading="loading" shadow="never" class="detail-panel">
      <el-form v-if="editing" label-position="top">
        <el-form-item label="Bug 标题" required><el-input v-model="bugForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="所属项目"><el-select v-model="bugForm.project_id" clearable filterable><el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" /></el-select></el-form-item>
          <el-form-item label="所属迭代"><el-select v-model="bugForm.iteration_id" clearable filterable><el-option v-for="iteration in editableIterationDisplayOptions" :key="iteration.id" :label="iteration.name" :value="iteration.id" :disabled="iteration.disabled" /></el-select></el-form-item>
          <el-form-item label="关联需求"><el-select v-model="bugForm.requirement_id" clearable filterable><el-option v-for="requirement in requirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item>
          <el-form-item label="关联任务"><el-select v-model="bugForm.task_id" clearable filterable><el-option v-for="task in tasks" :key="task.id" :label="task.title" :value="task.id" /></el-select></el-form-item>
          <el-form-item label="来源用例"><el-select v-model="bugForm.test_case_id" clearable filterable><el-option v-for="item in testCases" :key="item.id" :label="item.title" :value="item.id" /></el-select></el-form-item>
          <el-form-item label="提出人"><el-select v-model="bugForm.reporter_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="Bug 类型"><el-select v-model="bugForm.bug_type"><el-option v-for="option in bugTypeOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
          <el-form-item label="严重程度"><el-select v-model="bugForm.severity"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item>
          <el-form-item label="优先级"><el-select v-model="bugForm.priority"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item>
        </div>
        <el-form-item label="重现步骤"><RichTextPasteEditor v-model="bugForm.reproduce_steps" /></el-form-item>
        <el-form-item label="期望结果"><el-input v-model="bugForm.expected_result" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="实际结果"><el-input v-model="bugForm.actual_result" type="textarea" :rows="3" /></el-form-item>
      </el-form>

      <template v-else>
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
        <el-descriptions-item label="状态">{{ bug.status_name || '-' }}</el-descriptions-item>
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
      </template>
    </el-card>

    <el-card shadow="never" class="detail-panel">
      <template #header>
        <div class="detail-card-header">
          <span>关联任务</span>
          <LinkedTaskCreateButton
            v-if="bug.id"
            source-type="bug"
            :source-id="bugId"
            :source-title="bug.title"
            :users="users"
            @created="loadData"
          />
        </div>
      </template>
      <el-table :data="bug.linked_tasks || []" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="任务标题" min-width="220">
          <template #default="{ row }"><router-link class="table-link" :to="`/tasks/${row.id}`">{{ row.title }}</router-link></template>
        </el-table-column>
        <el-table-column label="任务分支" width="130"><template #default="{ row }">{{ taskBranchLabel(row.task_type) }}</template></el-table-column>
        <el-table-column label="处理人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column prop="status" label="状态" width="130" />
      </el-table>
    </el-card>

    <el-card shadow="never" class="detail-panel">
      <template #header>验证用例</template>
      <div class="validation-summary">
        <el-tag>{{ validationSourceLabel }}</el-tag>
        <el-tag>总数 {{ validationSummary.total || 0 }}</el-tag>
        <el-tag type="success">通过 {{ validationSummary.passed || 0 }}</el-tag>
        <el-tag type="warning">忽略 {{ validationSummary.ignored || 0 }}</el-tag>
        <el-tag type="danger">失败 {{ (validationSummary.failed || 0) + (validationSummary.blocked || 0) }}</el-tag>
        <el-tag type="info">未执行 {{ validationSummary.pending || 0 }}</el-tag>
      </div>
      <el-table :data="validationCases" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="用例标题" min-width="220">
          <template #default="{ row }"><router-link class="table-link" :to="{ name: 'test-case-detail', params: { id: row.id }, query: { from: 'bug' } }">{{ row.title }}</router-link></template>
        </el-table-column>
        <el-table-column label="测试人" width="140"><template #default="{ row }">{{ userLabel(users, row.default_tester_id) }}</template></el-table-column>
        <el-table-column label="最近结果" width="120"><template #default="{ row }">{{ executionResultLabel(row.latest_result) }}</template></el-table-column>
        <el-table-column label="最近执行时间" width="170"><template #default="{ row }">{{ formatDateTime(row.latest_execute_time) }}</template></el-table-column>
        <el-table-column label="未关闭Bug" width="110"><template #default="{ row }">{{ row.open_bug_count || 0 }}</template></el-table-column>
        <el-table-column label="操作" width="180" fixed="right"><template #default="{ row }"><el-button link type="success" @click="openCaseExecution(row)">执行</el-button><el-button v-if="canCreateBugFromCase(row)" link type="warning" @click="openCaseBug(row)">提 Bug</el-button></template></el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="caseExecutionVisible" :title="`执行用例 ${selectedCase?.title || ''}`" width="980px">
      <el-form label-position="top">
        <el-form-item label="执行时间"><el-date-picker v-model="caseExecutionForm.execute_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" /></el-form-item>
        <el-table :data="caseExecutionForm.steps_result_json" border>
          <el-table-column prop="step" label="步骤" min-width="220" />
          <el-table-column prop="expected" label="预期" min-width="220" />
          <el-table-column label="测试结果" width="140"><template #default="{ row }"><el-select v-model="row.result"><el-option v-for="option in executionResultOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></template></el-table-column>
          <el-table-column label="实际情况" min-width="220"><template #default="{ row }"><el-input v-model="row.actual" type="textarea" :rows="1" /></template></el-table-column>
        </el-table>
      </el-form>
      <template #footer><el-button @click="caseExecutionVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitCaseExecution">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="caseBugVisible" title="提交 Bug" width="820px">
      <el-form label-position="top">
        <el-form-item label="Bug 标题" required><el-input v-model="caseBugForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="Bug 类型"><el-select v-model="caseBugForm.bug_type"><el-option v-for="option in bugTypeOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
          <el-form-item label="严重程度"><el-select v-model="caseBugForm.severity"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item>
          <el-form-item label="优先级"><el-select v-model="caseBugForm.priority"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item>
        </div>
        <el-form-item label="重现步骤"><RichTextPasteEditor v-model="caseBugForm.reproduce_steps" /></el-form-item>
        <el-form-item label="实际结果"><el-input v-model="caseBugForm.actual_result" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="caseBugVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitCaseBug">保存</el-button></template>
    </el-dialog>

    <WorkItemCommentPanel
      v-if="bug.id"
      object-type="bug"
      :object-id="bugId"
      :users="users"
    />

    <CommitRecordsPanel object-type="bug" :object-id="bugId" />

<el-card id="history" shadow="never" class="detail-panel requirement-history-card">
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
                {{ item.from_state_name || '-' }} → {{ item.to_state_name || '-' }}
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

import { fetchBug, fetchBugStatusOperations, fetchBugValidationContext, updateBug } from '../api/bugs'
import { fetchIterations } from '../api/iterations'
import { fetchProjects } from '../api/projects'
import { fetchRequirements } from '../api/requirements'
import { fetchTasks } from '../api/tasks'
import { createBugFromTestCase, executeTestCase, fetchTestCase, fetchTestCaseExecutions, fetchTestCases } from '../api/testCases'
import { fetchUsers } from '../api/users'
import CommitRecordsPanel from '../components/CommitRecordsPanel.vue'
import LinkedTaskCreateButton from '../components/LinkedTaskCreateButton.vue'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import RichTextPasteEditor from '../components/RichTextPasteEditor.vue'
import WatchToggleButton from '../components/WatchToggleButton.vue'
import WorkItemCommentPanel from '../components/WorkItemCommentPanel.vue'
import WorkflowActionButtons from '../components/WorkflowActionButtons.vue'
import { labelById, userLabel } from '../utils/referenceLabels'
import { taskBranchLabel } from '../utils/taskBranchRules'
import { bugIterationOptions, includeSelectedIterationOption } from '../utils/bugIterations'
import { DEFAULT_BUG_TYPE_KEY } from '../utils/bugTypeOptions'
import { useBugTypes } from '../utils/useBugTypes'

const route = useRoute()
const router = useRouter()
const bugId = computed(() => Number(route.params.id))
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const bug = ref({})
const history = ref([])
const projects = ref([])
const iterations = ref([])
const requirements = ref([])
const tasks = ref([])
const testCases = ref([])
const users = ref([])
const bugForm = ref({})
const validationContext = ref({})
const validationCases = ref([])
const validationSummary = ref({})
const caseExecutionVisible = ref(false)
const caseBugVisible = ref(false)
const selectedCase = ref(null)
const bugSourceCase = ref(null)
const caseExecutionForm = ref({ execute_time: '', steps_result_json: [] })
const caseBugForm = ref({ title: '', bug_type: DEFAULT_BUG_TYPE_KEY, severity: '3', priority: '3', reproduce_steps: '', actual_result: '' })
const validationSourceLabel = computed(() => {
  if (validationContext.value.source === 'test_case') return '来源用例'
  if (validationContext.value.source === 'requirement') return '关联需求用例'
  return '暂无关联用例'
})
const editableIterationOptions = computed(() => bugIterationOptions(iterations.value, projects.value, bugForm.value.project_id))
const editableIterationDisplayOptions = computed(() => includeSelectedIterationOption(editableIterationOptions.value, iterations.value, bugForm.value.iteration_id))

const resolutionOptions = ['设计如此', '重复Bug', '外部原因', '已解决', '无法重现', '延期处理', '不予解决']
const { bugTypeOptions } = useBugTypes()
const priorityLevelOptions = [
  { label: '1级', value: '1' },
  { label: '2级', value: '2' },
  { label: '3级', value: '3' },
  { label: '4级', value: '4' },
  { label: '5级', value: '5' }
]
const actionOptions = [
  { label: '确认', value: 'confirm' },
  { label: '开始修复', value: 'start_fixing' },
  { label: '解决', value: 'resolve' },
  { label: '激活', value: 'activate' },
  { label: '挂起', value: 'suspend' },
  { label: '关闭', value: 'close' }
]
const executionResultOptions = [
  { label: '忽略', value: 'ignored' },
  { label: '通过', value: 'passed' },
  { label: '失败', value: 'failed' },
  { label: '阻塞', value: 'blocked' }
]

function optionLabel(options, value) {
  const option = options.find((item) => item.value === value)
  return option?.label || value || '-'
}
function actionLabel(value) { return optionLabel(actionOptions, value) }
function resolutionLabel(value) { return resolutionOptions.includes(value) ? value : value || '-' }
function executionResultLabel(value) { return optionLabel(executionResultOptions, value) }
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

function fillBugForm() {
  bugForm.value = {
    project_id: bug.value.project_id || null,
    iteration_id: bug.value.iteration_id || null,
    requirement_id: bug.value.requirement_id || null,
    task_id: bug.value.task_id || null,
    test_case_id: bug.value.test_case_id || null,
    test_run_id: bug.value.test_run_id || null,
    title: bug.value.title || '',
    bug_type: bug.value.bug_type || '代码错误',
    severity: String(bug.value.severity || '3'),
    priority: String(bug.value.priority || '3'),
    owner_id: bug.value.owner_id || null,
    reporter_id: bug.value.reporter_id || null,
    reproduce_steps: bug.value.reproduce_steps || '',
    expected_result: bug.value.expected_result || '',
    actual_result: bug.value.actual_result || ''
  }
}
function defaultExecutionTime() {
  const date = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
function normalizeCaseSteps(value) { return Array.isArray(value) && value.length ? value.map((item) => ({ step: item.step || '', expected: item.expected || '' })) : [{ step: '', expected: '' }] }
function canCreateBugFromCase(row) { return ['failed', 'blocked'].includes(row.latest_result || row.last_execute_result) }
async function openCaseExecution(row) {
  const { data } = await fetchTestCase(row.id)
  selectedCase.value = data
  caseExecutionForm.value = {
    execute_time: defaultExecutionTime(),
    steps_result_json: normalizeCaseSteps(data.steps_json).map((item) => ({ ...item, result: 'passed', actual: '' }))
  }
  caseExecutionVisible.value = true
}
async function submitCaseExecution() {
  saving.value = true
  try {
    await executeTestCase(selectedCase.value.id, { execute_time: caseExecutionForm.value.execute_time, steps_result_json: caseExecutionForm.value.steps_result_json })
    caseExecutionVisible.value = false
    await loadData()
    ElMessage.success('用例执行结果已保存')
  } finally {
    saving.value = false
  }
}
async function openCaseBug(row) {
  if (!canCreateBugFromCase(row)) return
  const [caseRes, historyRes] = await Promise.all([fetchTestCase(row.id), fetchTestCaseExecutions(row.id)])
  bugSourceCase.value = caseRes.data
  const latest = historyRes.data[0]
  caseBugForm.value = {
    title: bugSourceCase.value.title,
    bug_type: DEFAULT_BUG_TYPE_KEY,
    severity: '3',
    priority: '3',
    reproduce_steps: buildReproduceText(latest, bugSourceCase.value),
    actual_result: buildActualText(latest)
  }
  caseBugVisible.value = true
}
async function submitCaseBug() {
  if (!caseBugForm.value.title.trim()) return ElMessage.warning('请填写 Bug 标题')
  saving.value = true
  try {
    await createBugFromTestCase(bugSourceCase.value.id, { ...caseBugForm.value })
    caseBugVisible.value = false
    await loadData()
    ElMessage.success('Bug 已提交')
  } finally {
    saving.value = false
  }
}
function buildReproduceText(execution, testCase) {
  const rows = Array.isArray(execution?.steps_result_json) ? execution.steps_result_json : []
  if (!rows.length) return testCase.expected_result || ''
  return [
    '[步骤]',
    ...rows.map((row, index) => `${index + 1}. ${row.step || ''}`),
    '',
    '[结果]',
    ...rows.map((row, index) => `${index + 1}. ${executionResultLabel(row.result)} ${row.actual || ''}`),
    '',
    '[期望]',
    ...rows.map((row, index) => `${index + 1}. ${row.expected || ''}`)
  ].join('\n')
}
function buildActualText(execution) {
  const rows = Array.isArray(execution?.steps_result_json) ? execution.steps_result_json : []
  return rows.map((row) => row.actual).filter(Boolean).join('\n')
}
function startEdit() {
  fillBugForm()
  editing.value = true
}

function handleWorkflowCommand({ commandType }) {
  if (commandType === 'edit') startEdit()
  if (commandType === 'view_history') document.getElementById('history')?.scrollIntoView({ behavior: 'smooth' })
}
function cancelEdit() {
  editing.value = false
  fillBugForm()
}
async function saveBug() {
  if (!bugForm.value.title.trim()) return ElMessage.warning('请填写 Bug 标题')
  saving.value = true
  try {
    await updateBug(bugId.value, {
      ...bugForm.value,
      project_id: bugForm.value.project_id || null,
      iteration_id: bugForm.value.iteration_id || null,
      requirement_id: bugForm.value.requirement_id || null,
      task_id: bugForm.value.task_id || null,
      test_case_id: bugForm.value.test_case_id || null,
      test_run_id: bugForm.value.test_run_id || null,
      owner_id: bugForm.value.owner_id || null,
      reporter_id: bugForm.value.reporter_id || null
    })
    editing.value = false
    await loadData()
    ElMessage.success('Bug 已保存')
  } finally {
    saving.value = false
  }
}

async function loadData() {
  loading.value = true
  try {
    const [bugRes, historyRes, validationRes, projectRes, iterationRes, requirementRes, taskRes, testCaseRes, userRes] = await Promise.all([
      fetchBug(bugId.value),
      fetchBugStatusOperations(bugId.value),
      fetchBugValidationContext(bugId.value),
      fetchProjects(),
      fetchIterations(),
      fetchRequirements(),
      fetchTasks(),
      fetchTestCases(),
      fetchUsers()
    ])
    bug.value = bugRes.data
    history.value = historyRes.data
    validationContext.value = validationRes.data
    validationCases.value = validationRes.data.items || []
    validationSummary.value = validationRes.data.summary || {}
    projects.value = projectRes.data
    iterations.value = iterationRes.data
    requirements.value = requirementRes.data
    tasks.value = taskRes.data
    testCases.value = testCaseRes.data
    users.value = userRes.data
    fillBugForm()
  } catch {
    ElMessage.error('Bug 详情加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
