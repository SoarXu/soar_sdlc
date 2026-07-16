<template>
  <section class="requirement-detail-page">
    <div class="detail-titlebar">
      <el-button @click="goBackToProjectRequirements">返回</el-button>
      <el-tag effect="plain">#{{ requirement.id }}</el-tag>
      <h1>{{ requirement.title || '需求详情' }}</h1>
      <router-link v-if="requirement.project_id" class="detail-link" :to="`/projects/${requirement.project_id}`">进入项目</router-link>
      <WatchToggleButton v-if="requirement.id" object-type="requirement" :object-id="requirementId" />
      <WorkflowActionButtons
        v-if="!editing && requirement.id"
        object-type="requirement"
        :object-id="requirementId"
        mode="detail"
        :users="users"
        @command="handleWorkflowCommand"
        @executed="loadData"
      />
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
          <el-form-item label="提出人"><el-select v-model="requirementForm.proposer_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="类型"><el-select v-model="requirementForm.requirement_type"><el-option v-for="option in requirementTypeOptions" :key="option" :label="option" :value="option" /></el-select></el-form-item>
          <el-form-item label="优先级"><el-select v-model="requirementForm.priority"><el-option v-for="option in requirementPriorityOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item>
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
      <template #header>
        <div class="detail-card-header">
          <span>关联任务</span>
          <LinkedTaskCreateButton
            v-if="requirement.id"
            source-type="requirement"
            :source-id="requirementId"
            :source-title="requirement.title"
            :users="users"
            @created="loadData"
          />
        </div>
      </template>
      <el-table :data="relatedTasks" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="任务标题" min-width="220">
          <template #default="{ row }"><router-link class="table-link" :to="`/tasks/${row.id}`">{{ row.title }}</router-link></template>
        </el-table-column>
        <el-table-column label="任务分支" width="120"><template #default="{ row }">{{ taskBranchLabel(row.task_type) }}</template></el-table-column>
        <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column prop="status" label="状态" width="120" />
      </el-table>
    </el-card>

    <el-card shadow="never" class="detail-panel">
      <template #header>
        <div class="detail-card-header">
          <span>验证用例</span>
          <el-button type="primary" @click="openCaseCreateForRequirement">建用例</el-button>
        </div>
      </template>
      <div class="validation-summary">
        <el-tag>总数 {{ validationSummary.total || 0 }}</el-tag>
        <el-tag type="success">通过 {{ validationSummary.passed || 0 }}</el-tag>
        <el-tag type="warning">忽略 {{ validationSummary.ignored || 0 }}</el-tag>
        <el-tag type="danger">失败 {{ (validationSummary.failed || 0) + (validationSummary.blocked || 0) }}</el-tag>
        <el-tag type="info">未执行 {{ validationSummary.pending || 0 }}</el-tag>
      </div>
      <el-table :data="validationCases" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="用例标题" min-width="220">
          <template #default="{ row }"><router-link class="table-link" :to="{ name: 'test-case-detail', params: { id: row.id }, query: { from: 'requirement' } }">{{ row.title }}</router-link></template>
        </el-table-column>
        <el-table-column label="测试人" width="140"><template #default="{ row }">{{ userLabel(users, row.default_tester_id) }}</template></el-table-column>
        <el-table-column label="最近结果" width="120"><template #default="{ row }">{{ executionResultLabel(row.latest_result) }}</template></el-table-column>
        <el-table-column label="最近执行时间" width="170"><template #default="{ row }">{{ formatDateTime(row.latest_execute_time) || '-' }}</template></el-table-column>
        <el-table-column label="未关闭Bug" width="110"><template #default="{ row }">{{ row.open_bug_count || 0 }}</template></el-table-column>
        <el-table-column label="操作" width="180" fixed="right"><template #default="{ row }"><el-button link type="success" @click="openCaseExecution(row)">执行</el-button><el-button v-if="canCreateBugFromCase(row)" link type="warning" @click="openCaseBug(row)">提 Bug</el-button></template></el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="caseDialogVisible" title="新增用例" width="760px">
      <el-form label-position="top">
        <el-form-item label="用例标题" required><el-input v-model="caseForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="需求">
            <el-select v-model="caseForm.requirement_id" clearable filterable>
              <el-option :key="requirement.id" :label="requirement.title" :value="requirement.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="测试人">
            <el-select v-model="caseForm.default_tester_id" clearable filterable>
              <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="用例类型">
            <el-select v-model="caseForm.case_type">
              <el-option v-for="option in caseTypeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="适用范围">
            <el-select v-model="caseForm.test_scope">
              <el-option v-for="option in testScopeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="前置条件"><el-input v-model="caseForm.precondition" type="textarea" :rows="2" /></el-form-item>
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
        <el-form-item label="预期结果"><el-input v-model="caseForm.expected_result" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="caseDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitCase">保存</el-button></template>
    </el-dialog>

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
      v-if="requirement.id"
      object-type="requirement"
      :object-id="requirementId"
      :users="users"
    />

    <CommitRecordsPanel object-type="requirement" :object-id="requirementId" />

<el-card id="history" shadow="never" class="detail-panel requirement-history-card">
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
import { fetchRequirement, fetchRequirementAuditLogs, fetchRequirementStatusOperations, fetchRequirementValidationCases, updateRequirement } from '../api/requirements'
import { createBugFromTestCase, createTestCase, executeTestCase, fetchTestCase, fetchTestCaseExecutions } from '../api/testCases'
import { fetchTasks } from '../api/tasks'
import { fetchUsers } from '../api/users'
import CommitRecordsPanel from '../components/CommitRecordsPanel.vue'
import LinkedTaskCreateButton from '../components/LinkedTaskCreateButton.vue'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import RichTextPasteEditor from '../components/RichTextPasteEditor.vue'
import WatchToggleButton from '../components/WatchToggleButton.vue'
import WorkItemCommentPanel from '../components/WorkItemCommentPanel.vue'
import WorkflowActionButtons from '../components/WorkflowActionButtons.vue'
import { labelById, userLabel } from '../utils/referenceLabels'
import { formatAuditValue } from '../utils/auditHistoryLabels'
import { taskBranchLabel } from '../utils/taskBranchRules'
import { DEFAULT_BUG_TYPE_KEY } from '../utils/bugTypeOptions'
import { useBugTypes } from '../utils/useBugTypes'

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
const validationCases = ref([])
const validationSummary = ref({})
const caseDialogVisible = ref(false)
const caseExecutionVisible = ref(false)
const caseBugVisible = ref(false)
const selectedCase = ref(null)
const bugSourceCase = ref(null)
const caseExecutionForm = ref({ execute_time: '', steps_result_json: [] })
const caseForm = reactive({ project_id: null, requirement_id: null, title: '', case_type: 'functional', test_scope: 'functional_test', default_tester_id: null, precondition: '', steps_json: [{ step: '', expected: '' }], expected_result: '' })
const caseBugForm = reactive({ title: '', bug_type: DEFAULT_BUG_TYPE_KEY, severity: '3', priority: '3', reproduce_steps: '', actual_result: '' })
const expandedHistory = reactive({})
const requirementForm = reactive({ iteration_id: null, title: '', requirement_type: '功能', priority: '3', owner_id: null, proposer_id: null, description: '', acceptance_criteria: '' })
const relatedTasks = computed(() => (
  requirement.value.linked_tasks?.length
    ? requirement.value.linked_tasks
    : tasks.value.filter((item) => item.requirement_id === requirementId.value)
))
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
const requirementStatusOptions = [
  { label: '待分派', value: 'pending_assignment' },
  { label: '处理中', value: 'in_processing' },
  { label: '待确认', value: 'pending_confirmation' },
  { label: '已完成', value: 'completed' },
  { label: '已取消', value: 'canceled' }
]
const operationActionOptions = [
  { label: '认领', value: 'claim' },
  { label: '指派', value: 'assign' },
  { label: '转交', value: 'transfer' },
  { label: '完成', value: 'complete' },
  { label: '提交确认', value: 'submit_confirmation' },
  { label: '确认完成', value: 'confirm' },
  { label: '取消', value: 'cancel' },
  { label: '重新激活', value: 'reactivate' }
]
const requirementTypeOptions = ['功能', '接口', '性能', '安全', '体验', '改进', '其他']
const requirementPriorityOptions = [
  { label: '1级', value: '1' },
  { label: '2级', value: '2' },
  { label: '3级', value: '3' },
  { label: '4级', value: '4' },
  { label: '5级', value: '5' }
]
const executionResultOptions = [
  { label: '忽略', value: 'ignored' },
  { label: '通过', value: 'passed' },
  { label: '失败', value: 'failed' },
  { label: '阻塞', value: 'blocked' }
]
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
const { bugTypeOptions } = useBugTypes()
const priorityLevelOptions = [
  { label: '1级', value: '1' },
  { label: '2级', value: '2' },
  { label: '3级', value: '3' },
  { label: '4级', value: '4' },
  { label: '5级', value: '5' }
]

function optionLabel(options, value) { return options.find((option) => option.value === value)?.label || value || '-' }
function requirementStatusLabel(value) { return optionLabel(requirementStatusOptions, value) }
function operationActionLabel(value) { return optionLabel(operationActionOptions, value) }
function executionResultLabel(value) { return optionLabel(executionResultOptions, value) }
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
    { label: '需求描述', value: 'description' },
    { label: '验收标准', value: 'acceptance_criteria' }
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
    description: requirement.value.description || '',
    acceptance_criteria: requirement.value.acceptance_criteria || ''
  })
}
function defaultExecutionTime() {
  const date = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
function normalizeCaseSteps(value) { return Array.isArray(value) && value.length ? value.map((item) => ({ step: item.step || '', expected: item.expected || '' })) : [{ step: '', expected: '' }] }
function resetCaseForm() {
  Object.assign(caseForm, {
    project_id: requirement.value.project_id || null,
    requirement_id: requirement.value.id || requirementId.value,
    title: requirement.value.title || '',
    case_type: 'functional',
    test_scope: 'functional_test',
    default_tester_id: null,
    precondition: '',
    steps_json: [{ step: '', expected: '' }],
    expected_result: ''
  })
}
function openCaseCreateForRequirement() {
  resetCaseForm()
  caseDialogVisible.value = true
}
function addCaseStep() { caseForm.steps_json.push({ step: '', expected: '' }) }
function removeCaseStep(index) { if (caseForm.steps_json.length > 1) caseForm.steps_json.splice(index, 1) }
function cleanCaseSteps() { return caseForm.steps_json.filter((item) => item.step.trim() || item.expected.trim()) }
function canCreateBugFromCase(row) { return ['failed', 'blocked'].includes(row.latest_result || row.last_execute_result) }
async function submitCase() {
  if (!caseForm.title.trim()) return ElMessage.warning('请填写用例标题')
  saving.value = true
  try {
    await createTestCase({
      ...caseForm,
      project_id: requirement.value.project_id,
      requirement_id: requirement.value.id || requirementId.value,
      default_tester_id: caseForm.default_tester_id || null,
      steps_json: cleanCaseSteps()
    })
    caseDialogVisible.value = false
    await loadData()
    ElMessage.success('用例已创建')
  } finally {
    saving.value = false
  }
}
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
  Object.assign(caseBugForm, {
    title: bugSourceCase.value.title,
    bug_type: DEFAULT_BUG_TYPE_KEY,
    severity: '3',
    priority: '3',
    reproduce_steps: buildReproduceText(latest, bugSourceCase.value),
    actual_result: buildActualText(latest)
  })
  caseBugVisible.value = true
}
async function submitCaseBug() {
  if (!caseBugForm.title.trim()) return ElMessage.warning('请填写 Bug 标题')
  saving.value = true
  try {
    await createBugFromTestCase(bugSourceCase.value.id, { ...caseBugForm })
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
  fillRequirementForm()
  editing.value = true
}

function handleWorkflowCommand({ commandType }) {
  if (commandType === 'edit') startEdit()
  if (commandType === 'view_history') document.getElementById('history')?.scrollIntoView({ behavior: 'smooth' })
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
    const [requirementRes, projectRes, iterationRes, userRes, taskRes, validationRes, operationRes, auditRes] = await Promise.all([
      fetchRequirement(requirementId.value),
      fetchProjects(),
      fetchIterations(),
      fetchUsers(),
      fetchTasks(),
      fetchRequirementValidationCases(requirementId.value),
      fetchRequirementStatusOperations(requirementId.value),
      fetchRequirementAuditLogs(requirementId.value)
    ])
    requirement.value = requirementRes.data
    fillRequirementForm()
    projects.value = projectRes.data
    iterations.value = iterationRes.data
    users.value = userRes.data
    tasks.value = taskRes.data
    validationCases.value = validationRes.data.items || []
    validationSummary.value = validationRes.data.summary || {}
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
