<template>
  <section>
    <div class="page-head">
      <div>
        <h1>测试管理</h1>
        <p>维护测试用例库和测试单，关联项目、需求、迭代、人员和用例均以名称展示。</p>
      </div>
      <div class="page-actions"><el-button v-if="canManageAnyTestAsset" @click="openRunCreate">新增测试单</el-button><el-button v-if="canManageAnyTestAsset" type="primary" @click="openCaseCreate">新增用例</el-button></div>
    </div>

    <el-tabs v-model="activeTab">
      <el-tab-pane label="用例库" name="cases">
        <el-card shadow="never">
          <el-table v-loading="loading" :data="pagedTestCases" stripe>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column label="用例标题" min-width="220">
              <template #default="{ row }"><router-link class="table-link" :to="{ name: 'test-case-detail', params: { id: row.id } }">{{ row.title }}</router-link></template>
            </el-table-column>
            <el-table-column label="项目" width="170"><template #default="{ row }">{{ labelById(projects, row.project_id) }}</template></el-table-column>
            <el-table-column label="需求" width="180"><template #default="{ row }">{{ requirementLabel(row.requirement_id) }}</template></el-table-column>
            <el-table-column label="测试人" width="140"><template #default="{ row }">{{ userLabel(users, row.default_tester_id) }}</template></el-table-column>
            <el-table-column label="最近执行时间" width="170"><template #default="{ row }">{{ formatDateTime(row.last_execute_time) }}</template></el-table-column>
            <el-table-column label="最近结果" width="110"><template #default="{ row }">{{ executionResultLabel(row.last_execute_result) }}</template></el-table-column>
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="{ row }"><el-button v-if="canManageCaseRow(row)" link type="success" @click="openCaseExecution(row)">执行</el-button><el-button v-if="canManageCaseRow(row)" link type="warning" :disabled="!canCreateBugFromCase(row)" @click="openCaseBug(row)">提 Bug</el-button><el-button v-if="canManageCaseRow(row)" link type="primary" @click="openCaseEdit(row)">编辑</el-button><el-popconfirm v-if="canManageCaseRow(row)" title="确认删除该用例？" @confirm="removeCase(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template>
            </el-table-column>
          </el-table>
          <div class="table-pagination">
            <el-pagination
              v-model:current-page="casePage"
              v-model:page-size="casePageSize"
              :page-sizes="casePageSizes"
              :total="caseTotal"
              layout="total, sizes, prev, pager, next, jumper"
            />
          </div>
        </el-card>
      </el-tab-pane>
      <el-tab-pane label="测试单" name="runs">
        <el-card shadow="never">
          <el-table v-loading="loading" :data="pagedTestRuns" stripe>
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column prop="name" label="测试单名称" min-width="220" />
            <el-table-column label="项目" width="170"><template #default="{ row }">{{ labelById(projects, row.project_id) }}</template></el-table-column>
            <el-table-column label="迭代" width="160"><template #default="{ row }">{{ labelById(iterations, row.iteration_id) }}</template></el-table-column>
            <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.test_owner_id) }}</template></el-table-column>
            <el-table-column prop="status" label="状态" width="110" />
            <el-table-column label="操作" width="260" fixed="right">
              <template #default="{ row }"><el-button v-if="canManageRunRow(row)" link type="primary" @click="openRunEdit(row)">编辑</el-button><el-button v-if="canManageRunRow(row)" link type="success" @click="openSelectCases(row)">选用例</el-button><el-button v-if="canManageRunRow(row)" link type="warning" @click="openExecution">记录结果</el-button><el-popconfirm v-if="canManageRunRow(row)" title="确认删除该测试单？" @confirm="removeRun(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template>
            </el-table-column>
          </el-table>
          <div class="table-pagination">
            <el-pagination
              v-model:current-page="runPage"
              v-model:page-size="runPageSize"
              :page-sizes="runPageSizes"
              :total="runTotal"
              layout="total, sizes, prev, pager, next, jumper"
            />
          </div>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="caseDialogVisible" :title="editingCaseId ? '编辑用例' : '新增用例'" width="760px">
      <el-form label-position="top">
        <el-form-item label="用例标题" required><el-input v-model="caseForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目"><el-select v-model="caseForm.project_id" clearable filterable placeholder="请选择项目"><el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" /></el-select></el-form-item>
          <el-form-item label="需求"><el-select v-model="caseForm.requirement_id" clearable filterable placeholder="请选择需求"><el-option v-for="requirement in requirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item>
          <el-form-item label="测试人"><el-select v-model="caseForm.default_tester_id" clearable filterable placeholder="请选择测试人"><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="用例类型"><el-select v-model="caseForm.case_type"><el-option v-for="option in caseTypeOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
        </div>
        <div class="form-grid"><el-form-item label="适用范围"><el-select v-model="caseForm.test_scope"><el-option v-for="option in testScopeOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item></div>
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
      <div class="execution-history">
        <h3>测试结果</h3>
        <p>共执行 {{ caseExecutionHistory.length }} 次，失败 {{ failedExecutionCount }} 次</p>
        <el-collapse>
          <el-collapse-item v-for="item in caseExecutionHistory" :key="item.id" :title="executionHistoryTitle(item)" :name="item.id">
            <el-table :data="item.steps_result_json || []" border>
              <el-table-column prop="step" label="步骤" min-width="220" />
              <el-table-column prop="expected" label="预期" min-width="220" />
              <el-table-column label="测试结果" width="120"><template #default="{ row }">{{ executionResultLabel(row.result) }}</template></el-table-column>
              <el-table-column prop="actual" label="实际情况" min-width="220" />
            </el-table>
          </el-collapse-item>
        </el-collapse>
      </div>
      <template #footer><el-button @click="caseExecutionVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitCaseExecution">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="caseBugVisible" title="提交 Bug" width="820px">
      <el-form label-position="top">
        <el-form-item label="Bug 标题" required><el-input v-model="caseBugForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="Bug 类型"><el-select v-model="caseBugForm.bug_type"><el-option v-for="option in bugTypeOptions" :key="option" :label="option" :value="option" /></el-select></el-form-item>
          <el-form-item label="严重程度"><el-select v-model="caseBugForm.severity"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
          <el-form-item label="优先级"><el-select v-model="caseBugForm.priority"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
        </div>
        <el-form-item label="重现步骤"><RichTextPasteEditor v-model="caseBugForm.reproduce_steps" /></el-form-item>
        <el-form-item label="实际结果"><el-input v-model="caseBugForm.actual_result" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="caseBugVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitCaseBug">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="runDialogVisible" :title="editingRunId ? '编辑测试单' : '新增测试单'" width="560px">
      <el-form label-position="top">
        <el-form-item label="测试单名称" required><el-input v-model="runForm.name" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目" required><el-select v-model="runForm.project_id" filterable placeholder="请选择项目"><el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" /></el-select></el-form-item>
          <el-form-item label="迭代"><el-select v-model="runForm.iteration_id" clearable filterable placeholder="请选择迭代"><el-option v-for="iteration in iterations" :key="iteration.id" :label="iteration.name" :value="iteration.id" /></el-select></el-form-item>
          <el-form-item label="测试负责人"><el-select v-model="runForm.test_owner_id" clearable filterable placeholder="请选择负责人"><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="状态"><el-select v-model="runForm.status"><el-option label="规划中" value="planning" /><el-option label="执行中" value="running" /><el-option label="完成" value="finished" /></el-select></el-form-item>
        </div>
        <el-form-item label="备注"><el-input v-model="runForm.remark" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="runDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRun">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="selectDialogVisible" title="选择测试用例" width="520px">
      <el-form label-position="top">
        <el-form-item label="测试单"><el-input :model-value="labelById(testRuns, selectedRunId, 'name')" disabled /></el-form-item>
        <el-form-item label="测试用例" required><el-select v-model="selectForm.test_case_ids" multiple filterable placeholder="请选择测试用例"><el-option v-for="item in testCases" :key="item.id" :label="item.title" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="执行人"><el-select v-model="selectForm.tester_id" clearable filterable placeholder="请选择执行人"><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
      </el-form>
      <template #footer><el-button @click="selectDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitSelectCases">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="executionDialogVisible" title="记录执行结果" width="520px">
      <el-form label-position="top">
        <el-form-item label="测试单用例" required><el-select v-model="executionForm.run_case_id" filterable placeholder="请选择执行记录"><el-option v-for="item in testRunCases" :key="item.id" :label="runCaseLabel(item)" :value="item.id" /></el-select></el-form-item>
        <el-form-item label="结果"><el-select v-model="executionForm.result"><el-option label="通过" value="passed" /><el-option label="失败" value="failed" /><el-option label="阻塞" value="blocked" /></el-select></el-form-item>
        <el-form-item label="备注"><el-input v-model="executionForm.remark" type="textarea" :rows="3" /></el-form-item>
        <el-form-item v-if="executionForm.result === 'failed'" label="失败后创建 Bug 标题"><el-input v-model="executionForm.bug_title" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="executionDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitExecution">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import RichTextPasteEditor from '../components/RichTextPasteEditor.vue'
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchIterations } from '../api/iterations'
import { fetchProjectMembers, fetchProjects } from '../api/projects'
import { fetchRequirements } from '../api/requirements'
import { createBugFromTestCase, createTestCase, deleteTestCase, executeTestCase, fetchTestCaseExecutions, fetchTestCases, updateTestCase } from '../api/testCases'
import { createBugFromTestRunCase, createTestRun, deleteTestRun, fetchTestRunCases, fetchTestRuns, selectTestCases, updateTestRun, updateTestRunCase } from '../api/testRuns'
import { fetchUsers } from '../api/users'
import { showActionError } from '../utils/actionFeedback'
import { canManageTestCase, currentUserFromStorage } from '../utils/permissions'
import { labelById, userLabel } from '../utils/referenceLabels'
import { usePagination } from '../utils/usePagination'

const activeTab = ref('cases'), saving = ref(false), loading = ref(false)
const testCases = ref([]), testRuns = ref([]), testRunCases = ref([]), projects = ref([]), requirements = ref([]), iterations = ref([]), users = ref([])
const projectMembersById = ref({})
const {
  page: casePage,
  pageSize: casePageSize,
  pageSizes: casePageSizes,
  total: caseTotal,
  pagedItems: pagedTestCases
} = usePagination(testCases)
const {
  page: runPage,
  pageSize: runPageSize,
  pageSizes: runPageSizes,
  total: runTotal,
  pagedItems: pagedTestRuns
} = usePagination(testRuns)
const caseDialogVisible = ref(false), runDialogVisible = ref(false), selectDialogVisible = ref(false), executionDialogVisible = ref(false), caseExecutionVisible = ref(false), caseBugVisible = ref(false)
const editingCaseId = ref(null), editingRunId = ref(null), selectedRunId = ref(null)
const selectedCase = ref(null)
const bugSourceCase = ref(null)
const caseExecutionHistory = ref([])
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
const bugTypeOptions = ['代码错误', '配置相关', '安装部署', '安全相关', '性能问题', '标准规范', '测试脚本', '设计缺陷', '其他']
const priorityLevelOptions = [
  { label: '① 最高', value: '1' },
  { label: '② 高', value: '2' },
  { label: '③ 中', value: '3' },
  { label: '④ 低', value: '4' },
  { label: '⑤ 最低', value: '5' }
]
const caseForm = reactive({ project_id: null, requirement_id: null, title: '', case_type: 'functional', test_scope: 'functional_test', default_tester_id: null, precondition: '', steps_json: [{ step: '', expected: '' }], expected_result: '' })
const caseExecutionForm = reactive({ execute_time: '', steps_result_json: [] })
const caseBugForm = reactive({ title: '', bug_type: '代码错误', severity: '3', priority: '3', reproduce_steps: '', actual_result: '' })
const runForm = reactive({ project_id: null, iteration_id: null, name: '', test_owner_id: null, status: 'planning', remark: '' })
const selectForm = reactive({ test_case_ids: [], tester_id: null })
const executionForm = reactive({ run_case_id: null, result: 'passed', remark: '', bug_title: '' })
const currentUser = computed(() => currentUserFromStorage(users.value))
const canManageAnyTestAsset = computed(() => projects.value.some((project) => canManageTestCase(project, currentUser.value, membersForProject(project.id))))

function runCaseLabel(item) { return `${labelById(testRuns.value, item.test_run_id, 'name')} / ${labelById(testCases.value, item.test_case_id, 'title')} / ${item.result}` }
function membersForProject(projectId) { return projectMembersById.value[projectId] || [] }
function projectForId(projectId) { return projects.value.find((item) => item.id === projectId) || null }
function canManageCaseRow(row) { return canManageTestCase(projectForId(row.project_id), currentUser.value, membersForProject(row.project_id)) }
function canManageRunRow(row) { return canManageTestCase(projectForId(row.project_id), currentUser.value, membersForProject(row.project_id)) }
function requirementLabel(requirementId) {
  if (!requirementId) return '-'
  return requirements.value.find((item) => item.id === requirementId)?.title || '-'
}
function normalizeCaseSteps(value) { return Array.isArray(value) && value.length ? value.map((item) => ({ step: item.step || '', expected: item.expected || '' })) : [{ step: '', expected: '' }] }
function addCaseStep() { caseForm.steps_json.push({ step: '', expected: '' }) }
function removeCaseStep(index) { if (caseForm.steps_json.length > 1) caseForm.steps_json.splice(index, 1) }
function cleanCaseSteps() { return caseForm.steps_json.filter((item) => item.step.trim() || item.expected.trim()) }
const failedExecutionCount = computed(() => caseExecutionHistory.value.filter((item) => item.result === 'failed').length)
function formatDateTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-' }
function executionResultLabel(value) { return executionResultOptions.find((option) => option.value === value)?.label || '-' }
function executionHistoryTitle(item) { return `#${item.id} ${formatDateTime(item.execute_time)}，结果为 ${executionResultLabel(item.result)}` }
function canCreateBugFromCase(row) { return ['failed', 'blocked'].includes(row.last_execute_result) }
function defaultExecutionTime() {
  const date = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
function openCaseCreate() { editingCaseId.value = null; Object.assign(caseForm, { project_id: null, requirement_id: null, title: '', case_type: 'functional', test_scope: 'functional_test', default_tester_id: null, precondition: '', steps_json: [{ step: '', expected: '' }], expected_result: '' }); caseDialogVisible.value = true }
function openCaseEdit(row) { editingCaseId.value = row.id; Object.assign(caseForm, { ...row, case_type: row.case_type || 'functional', test_scope: row.test_scope || 'functional_test', precondition: row.precondition || '', steps_json: normalizeCaseSteps(row.steps_json), expected_result: row.expected_result || '' }); caseDialogVisible.value = true }
async function openCaseExecution(row) {
  selectedCase.value = row
  Object.assign(caseExecutionForm, {
    execute_time: defaultExecutionTime(),
    steps_result_json: normalizeCaseSteps(row.steps_json).map((item) => ({ ...item, result: 'passed', actual: '' }))
  })
  caseExecutionHistory.value = (await fetchTestCaseExecutions(row.id)).data
  caseExecutionVisible.value = true
}
async function openCaseBug(row) {
  if (!canCreateBugFromCase(row)) return
  bugSourceCase.value = row
  const history = (await fetchTestCaseExecutions(row.id)).data
  const latest = history[0]
  Object.assign(caseBugForm, {
    title: row.title,
    bug_type: '代码错误',
    severity: '3',
    priority: '3',
    reproduce_steps: buildReproduceText(latest, row),
    actual_result: buildActualText(latest)
  })
  caseBugVisible.value = true
}
function openRunCreate() { editingRunId.value = null; Object.assign(runForm, { project_id: null, iteration_id: null, name: '', test_owner_id: null, status: 'planning', remark: '' }); runDialogVisible.value = true }
function openRunEdit(row) { editingRunId.value = row.id; Object.assign(runForm, { ...row, remark: row.remark || '' }); runDialogVisible.value = true }
function openSelectCases(row) { selectedRunId.value = row.id; selectForm.test_case_ids = []; selectForm.tester_id = null; selectDialogVisible.value = true }
async function openExecution() { Object.assign(executionForm, { run_case_id: null, result: 'passed', remark: '', bug_title: '' }); await loadRunCases(); executionDialogVisible.value = true }

async function loadData() {
  loading.value = true
  try {
    const [caseRes, runRes, runCaseRes, projectRes, reqRes, iterationRes, userRes] = await Promise.all([fetchTestCases(), fetchTestRuns(), fetchTestRunCases(), fetchProjects(), fetchRequirements(), fetchIterations(), fetchUsers()])
    testCases.value = caseRes.data; testRuns.value = runRes.data; testRunCases.value = runCaseRes.data; projects.value = projectRes.data; requirements.value = reqRes.data; iterations.value = iterationRes.data; users.value = userRes.data
    await loadProjectMembers()
  } catch { ElMessage.error('测试管理数据加载失败') } finally { loading.value = false }
}
async function loadProjectMembers() {
  const entries = await Promise.all(projects.value.map(async (project) => {
    try {
      const { data } = await fetchProjectMembers(project.id)
      return [project.id, data]
    } catch {
      return [project.id, []]
    }
  }))
  projectMembersById.value = Object.fromEntries(entries)
}
async function loadRunCases() { testRunCases.value = (await fetchTestRunCases()).data }
async function submitCase() { if (!caseForm.title.trim()) return ElMessage.warning('请填写用例标题'); saving.value = true; try { const payload = { ...caseForm, project_id: caseForm.project_id || null, requirement_id: caseForm.requirement_id || null, default_tester_id: caseForm.default_tester_id || null, steps_json: cleanCaseSteps() }; if (editingCaseId.value) await updateTestCase(editingCaseId.value, payload); else await createTestCase(payload); caseDialogVisible.value = false; await loadData() } catch (error) { showActionError(error, editingCaseId.value ? '用例保存失败' : '用例创建失败') } finally { saving.value = false } }
async function submitCaseExecution() { saving.value = true; try { const currentId = selectedCase.value.id; await executeTestCase(currentId, { execute_time: caseExecutionForm.execute_time, steps_result_json: caseExecutionForm.steps_result_json }); await loadData(); ElMessage.success('用例执行结果已保存'); await openNextCaseAfterExecution(currentId, pagedTestCases.value) } catch (error) { showActionError(error, '用例执行结果保存失败') } finally { saving.value = false } }
async function submitCaseBug() { if (!caseBugForm.title.trim()) return ElMessage.warning('请填写 Bug 标题'); saving.value = true; try { await createBugFromTestCase(bugSourceCase.value.id, { ...caseBugForm }); caseBugVisible.value = false; await loadData(); ElMessage.success('Bug 已提交') } catch (error) { showActionError(error, 'Bug 提交失败') } finally { saving.value = false } }
async function submitRun() { if (!runForm.project_id || !runForm.name.trim()) return ElMessage.warning('请选择项目并填写测试单名称'); saving.value = true; try { const payload = { ...runForm, iteration_id: runForm.iteration_id || null, test_owner_id: runForm.test_owner_id || null }; if (editingRunId.value) await updateTestRun(editingRunId.value, payload); else await createTestRun(payload); runDialogVisible.value = false; await loadData() } catch (error) { showActionError(error, editingRunId.value ? '测试单保存失败' : '测试单创建失败') } finally { saving.value = false } }
async function submitSelectCases() { if (!selectForm.test_case_ids.length) return ElMessage.warning('请选择测试用例'); saving.value = true; try { await selectTestCases(selectedRunId.value, { test_case_ids: selectForm.test_case_ids, tester_id: selectForm.tester_id || null }); selectDialogVisible.value = false; await loadData(); ElMessage.success('用例已加入测试单') } catch (error) { showActionError(error, '选择用例失败') } finally { saving.value = false } }
async function submitExecution() { if (!executionForm.run_case_id) return ElMessage.warning('请选择执行记录'); saving.value = true; try { await updateTestRunCase(executionForm.run_case_id, { result: executionForm.result, remark: executionForm.remark }); if (executionForm.result === 'failed' && executionForm.bug_title.trim()) await createBugFromTestRunCase(executionForm.run_case_id, { title: executionForm.bug_title, actual_result: executionForm.remark }); executionDialogVisible.value = false; await loadData(); ElMessage.success('执行结果已保存') } catch (error) { showActionError(error, '执行结果保存失败') } finally { saving.value = false } }
async function removeCase(id) { try { await deleteTestCase(id); await loadData() } catch (error) { showActionError(error, '用例删除失败') } }
async function removeRun(id) { try { await deleteTestRun(id); await loadData() } catch (error) { showActionError(error, '测试单删除失败') } }
onMounted(loadData)

async function openNextCaseAfterExecution(currentId, rows) {
  const index = rows.findIndex((item) => item.id === currentId)
  const next = index >= 0 ? rows[index + 1] : null
  if (next) await openCaseExecution(next)
  else caseExecutionVisible.value = false
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
</script>
