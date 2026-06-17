<template>
  <section class="workbench-page">
    <div class="page-head">
      <div>
        <h1>工作台</h1>
        <p>按迭代和负责人聚合当前需要处理的需求、任务、测试用例和 Bug。</p>
      </div>
      <div class="page-actions">
        <el-select v-model="ownerFilter" clearable filterable placeholder="负责人" class="workbench-filter">
          <el-option v-for="owner in owners" :key="owner.id" :label="owner.full_name" :value="owner.id" />
        </el-select>
        <el-select v-model="typeFilter" clearable placeholder="类型" class="workbench-filter">
          <el-option v-for="type in itemTypes" :key="type.value" :label="type.label" :value="type.value" />
        </el-select>
        <el-button :loading="loading" @click="loadWorkbench">刷新</el-button>
      </div>
    </div>

    <div class="workbench-summary">
      <el-card v-for="item in summaryCards" :key="item.key" shadow="never">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </el-card>
    </div>

    <div v-loading="loading" class="workbench-board">
      <article v-for="iteration in filteredIterations" :key="iteration.id" class="iteration-board">
        <header class="iteration-board-head">
          <div>
            <h2>{{ iteration.name }}</h2>
            <span>{{ iterationStatusLabel(iteration.status) }} · {{ iteration.start_date || '-' }} 至 {{ iteration.end_date || '-' }}</span>
          </div>
          <el-tag>{{ boardTotal(iteration) }} 项</el-tag>
        </header>

        <div class="workbench-lanes">
          <section v-for="group in visibleGroups(iteration)" :key="`${iteration.id}-${group.key}`" class="workbench-lane">
            <header>
              <span>{{ group.label }}</span>
              <strong>{{ group.items.length }}</strong>
            </header>
            <VueDraggable
              v-model="group.items"
              class="workbench-card-list"
              :group="{ name: group.key }"
              item-key="drag_key"
              ghost-class="workbench-card-ghost"
              chosen-class="workbench-card-chosen"
              @start="onDragStart"
              @add="(event) => onDragAdd(event, group.key, iteration.id)"
            >
              <div v-for="item in group.items" :key="item.drag_key" class="workbench-card" :data-id="item.id">
                <div class="workbench-card-top">
                  <el-tag size="small" :type="typeTag(item.object_type)">{{ typeLabel(item.object_type) }}</el-tag>
                  <span class="workbench-status">{{ itemStatusLabel(item) }}</span>
                </div>
                <router-link class="workbench-title" :to="detailLink(item)">{{ item.title }}</router-link>
                <p>{{ item.project_name || '-' }}</p>
                <div class="workbench-meta">
                  <span>{{ ownerName(item.owner_id) }}</span>
                  <RequirementPriorityBadge v-if="item.priority || item.severity" :value="item.severity || item.priority" />
                  <span v-if="item.due_date">截止 {{ item.due_date }}</span>
                  <span v-if="item.last_execute_result">最近 {{ executionResultLabel(item.last_execute_result) }}</span>
                </div>
                <div class="workbench-actions">
                  <template v-if="item.object_type === 'requirement'">
                    <el-button v-if="['draft', 'closed'].includes(item.status)" link type="warning" @click="activateRequirementRow(item)">激活</el-button>
                    <el-button v-if="item.status === 'active'" link type="success" @click="completeRequirementRow(item)">完成</el-button>
                    <el-button v-if="item.status === 'active'" link type="danger" @click="openRequirementClose(item)">关闭</el-button>
                  </template>
                  <template v-else-if="item.object_type === 'task'">
                    <el-button v-if="['todo', 'closed'].includes(item.status)" link type="warning" @click="activateTaskRow(item)">激活</el-button>
                    <el-button v-if="item.status === 'doing'" link type="success" @click="completeTaskRow(item)">完成</el-button>
                    <el-button v-if="item.status !== 'closed'" link type="danger" @click="openTaskClose(item)">关闭</el-button>
                  </template>
                  <template v-else-if="item.object_type === 'test_case'">
                    <el-button link type="success" @click="openCaseExecution(item)">执行</el-button>
                    <el-button link type="warning" :disabled="!canCreateBugFromCase(item)" @click="openCaseBug(item)">提 Bug</el-button>
                  </template>
                  <template v-else-if="item.object_type === 'bug'">
                    <el-button v-if="['open', 'reopened', 'suspended'].includes(item.status)" link type="success" @click="openBugAction(item, 'start_fixing')">确认</el-button>
                    <el-button v-if="item.status === 'fixing'" link type="success" @click="openBugAction(item, 'resolve')">解决</el-button>
                    <el-button v-if="item.status === 'verifying'" link type="success" @click="openBugAction(item, 'verify_passed')">验证通过</el-button>
                    <el-button v-if="item.status === 'verifying'" link type="danger" @click="openBugAction(item, 'verify_failed')">验证失败</el-button>
                    <el-button v-if="['verifying', 'closed'].includes(item.status)" link type="warning" @click="openBugAction(item, 'activate')">激活</el-button>
                    <el-button v-if="['open', 'fixing', 'reopened'].includes(item.status)" link type="warning" @click="openBugAction(item, 'suspend')">挂起</el-button>
                    <el-button v-if="['open', 'suspended', 'verifying'].includes(item.status)" link type="danger" @click="openBugAction(item, 'close')">关闭</el-button>
                  </template>
                </div>
              </div>
            </VueDraggable>
          </section>
        </div>
      </article>
    </div>

    <el-dialog v-model="closeRequirementVisible" title="关闭需求" width="480px">
      <el-form label-position="top">
        <el-form-item label="关闭原因" required>
          <el-select v-model="closeForm.reason">
            <el-option v-for="option in closeReasons" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="closeForm.remark" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="closeRequirementVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRequirementClose">确认关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="closeTaskVisible" title="关闭任务" width="480px">
      <el-form label-position="top">
        <el-form-item label="关闭原因" required>
          <el-select v-model="closeForm.reason">
            <el-option v-for="option in closeReasons" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="closeForm.remark" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="closeTaskVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitTaskClose">确认关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="bugActionVisible" :title="bugActionTitle" width="560px">
      <el-form label-position="top">
        <el-form-item v-if="bugActionType === 'start_fixing'" label="解决迭代">
          <el-select v-model="bugActionForm.iteration_id" clearable filterable>
            <el-option v-for="iteration in iterations" :key="iteration.id" :label="iteration.name" :value="iteration.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="bugActionType === 'resolve'" label="解决方案" required>
          <el-select v-model="bugActionForm.resolution">
            <el-option v-for="option in bugResolutionOptions" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="bugActionForm.remark" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="bugActionVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitBugAction">确认</el-button></template>
    </el-dialog>

    <el-dialog v-model="caseExecutionVisible" :title="`执行用例 ${selectedCase?.title || ''}`" width="760px">
      <el-form label-position="top">
        <el-form-item label="执行时间"><el-date-picker v-model="caseExecutionForm.execute_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" /></el-form-item>
        <el-table :data="caseExecutionForm.steps_result_json" border>
          <el-table-column prop="step" label="步骤" min-width="180" />
          <el-table-column prop="expected" label="预期" min-width="180" />
          <el-table-column label="测试结果" width="140"><template #default="{ row }"><el-select v-model="row.result"><el-option v-for="option in executionResultOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></template></el-table-column>
          <el-table-column label="实际情况" min-width="180"><template #default="{ row }"><el-input v-model="row.actual" type="textarea" :rows="1" /></template></el-table-column>
        </el-table>
      </el-form>
      <template #footer><el-button @click="caseExecutionVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitCaseExecution">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="caseBugVisible" title="提交 Bug" width="620px">
      <el-form label-position="top">
        <el-form-item label="Bug 标题" required><el-input v-model="caseBugForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="Bug 类型"><el-select v-model="caseBugForm.bug_type"><el-option v-for="option in bugTypeOptions" :key="option" :label="option" :value="option" /></el-select></el-form-item>
          <el-form-item label="严重程度"><el-select v-model="caseBugForm.severity"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
        </div>
        <el-form-item label="重现步骤"><el-input v-model="caseBugForm.reproduce_steps" type="textarea" :rows="6" /></el-form-item>
        <el-form-item label="实际结果"><el-input v-model="caseBugForm.actual_result" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="caseBugVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitCaseBug">提交</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { VueDraggable } from 'vue-draggable-plus'
import { ElMessage, ElMessageBox } from 'element-plus'

import { fetchWorkbench, moveWorkbenchItem } from '../api/dashboard'
import { activateRequirement, closeRequirement, completeRequirement } from '../api/requirements'
import { activateTask, closeTask, completeTask } from '../api/tasks'
import { createBugFromTestCase, executeTestCase } from '../api/testCases'
import { activateBug, closeBug, resolveBug, startFixingBug, suspendBug, verifyBugFailed, verifyBugPassed } from '../api/bugs'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'

const loading = ref(false)
const saving = ref(false)
const iterations = ref([])
const owners = ref([])
const ownerFilter = ref(null)
const typeFilter = ref('')
const dragSnapshot = ref(null)
const selectedRequirement = ref(null)
const selectedTask = ref(null)
const selectedBug = ref(null)
const selectedCase = ref(null)
const closeRequirementVisible = ref(false)
const closeTaskVisible = ref(false)
const bugActionVisible = ref(false)
const bugActionType = ref('')
const caseExecutionVisible = ref(false)
const caseBugVisible = ref(false)
const closeForm = reactive({ reason: '', remark: '' })
const bugActionForm = reactive({ iteration_id: null, resolution: '已解决', remark: '' })
const caseExecutionForm = reactive({ execute_time: '', steps_result_json: [] })
const caseBugForm = reactive({ title: '', bug_type: '代码错误', severity: '3', priority: '3', reproduce_steps: '', actual_result: '' })

const itemTypes = [
  { label: '需求', value: 'requirement' },
  { label: '任务', value: 'task' },
  { label: '测试用例', value: 'test_case' },
  { label: 'Bug', value: 'bug' }
]
const closeReasons = ['已完成', '不做', '重复', '延期', '其他']
const bugResolutionOptions = ['设计如此', '重复Bug', '外部原因', '已解决', '无法重现', '延期处理', '不予解决']
const bugTypeOptions = ['代码错误', '配置相关', '安装部署', '安全相关', '性能问题', '标准规范', '测试脚本', '设计缺陷', '其他']
const priorityLevelOptions = [
  { label: '① 最高', value: '1' },
  { label: '② 高', value: '2' },
  { label: '③ 中', value: '3' },
  { label: '④ 低', value: '4' },
  { label: '⑤ 最低', value: '5' }
]
const executionResultOptions = [
  { label: '忽略', value: 'ignored' },
  { label: '通过', value: 'passed' },
  { label: '失败', value: 'failed' },
  { label: '阻塞', value: 'blocked' }
]
const statusOptions = {
  iteration: { planning: '规划中', active: '进行中', finished: '已完成', closed: '已关闭' },
  requirement: { draft: '草稿', active: '激活', done: '完成', closed: '关闭' },
  task: { todo: '待办', doing: '进行中', done: '完成', closed: '关闭' },
  bug: { open: '待确认', fixing: '修复中', resolved: '已解决', verifying: '待验证', closed: '已关闭', reopened: '重新打开', suspended: '已挂起' }
}

const filteredIterations = computed(() => iterations.value.map((iteration) => ({
  ...iteration,
  requirements: filterItems(iteration.requirements || []),
  tasks: filterItems(iteration.tasks || []),
  test_cases: filterItems(iteration.test_cases || []),
  bugs: filterItems(iteration.bugs || [])
})).filter((iteration) => boardTotal(iteration) > 0))

const summaryCards = computed(() => {
  const boards = filteredIterations.value
  return [
    { key: 'iterations', label: '迭代板块', value: boards.length },
    { key: 'requirements', label: '需求', value: boards.reduce((sum, item) => sum + item.requirements.length, 0) },
    { key: 'tasks', label: '任务', value: boards.reduce((sum, item) => sum + item.tasks.length, 0) },
    { key: 'test_cases', label: '测试用例', value: boards.reduce((sum, item) => sum + item.test_cases.length, 0) },
    { key: 'bugs', label: 'Bug', value: boards.reduce((sum, item) => sum + item.bugs.length, 0) }
  ]
})

const bugActionTitle = computed(() => ({ start_fixing: '确认 Bug', resolve: '解决 Bug', activate: '激活 Bug', suspend: '挂起 Bug', close: '关闭 Bug' }[bugActionType.value] || 'Bug 操作'))

function filterItems(items) {
  return items
    .filter((item) => !ownerFilter.value || item.owner_id === ownerFilter.value)
    .filter((item) => !typeFilter.value || item.object_type === typeFilter.value)
    .map((item) => ({ ...item, drag_key: `${item.object_type}-${item.id}` }))
}
function visibleGroups(iteration) {
  return [
    { key: 'requirement', label: '需求', items: iteration.requirements || [] },
    { key: 'task', label: '任务', items: iteration.tasks || [] },
    { key: 'test_case', label: '测试用例', items: iteration.test_cases || [] },
    { key: 'bug', label: 'Bug', items: iteration.bugs || [] }
  ].filter((group) => !typeFilter.value || group.key === typeFilter.value)
}
function boardTotal(iteration) { return (iteration.requirements?.length || 0) + (iteration.tasks?.length || 0) + (iteration.test_cases?.length || 0) + (iteration.bugs?.length || 0) }
function ownerName(id) { return owners.value.find((item) => item.id === id)?.full_name || '未分配' }
function typeLabel(value) { return itemTypes.find((item) => item.value === value)?.label || value }
function typeTag(value) { return { requirement: 'primary', task: 'success', test_case: 'warning', bug: 'danger' }[value] || 'info' }
function iterationStatusLabel(value) { return statusOptions.iteration[value] || value || '-' }
function itemStatusLabel(item) { return item.object_type === 'test_case' ? executionResultLabel(item.last_execute_result) : (statusOptions[item.object_type]?.[item.status] || item.status || '-') }
function executionResultLabel(value) { return executionResultOptions.find((item) => item.value === value)?.label || value || '未执行' }
function canCreateBugFromCase(item) { return ['failed', 'blocked'].includes(item.last_execute_result) }
function detailLink(item) {
  if (item.object_type === 'requirement') return { name: 'requirement-detail', params: { id: item.id }, query: { from: 'dashboard' } }
  if (item.object_type === 'task') return { name: 'task-detail', params: { id: item.id }, query: { from: 'dashboard' } }
  if (item.object_type === 'test_case') return { name: 'test-case-detail', params: { id: item.id }, query: { from: 'dashboard' } }
  return { name: 'bug-detail', params: { id: item.id }, query: { from: 'dashboard' } }
}
function defaultExecutionTime() {
  const date = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

async function loadWorkbench() {
  loading.value = true
  try {
    const { data } = await fetchWorkbench()
    iterations.value = data.iterations || []
    owners.value = data.owners || []
  } catch (error) {
    ElMessage.error('工作台加载失败，请确认后端服务已启动')
  } finally {
    loading.value = false
  }
}
function onDragStart() {
  dragSnapshot.value = JSON.parse(JSON.stringify(iterations.value))
}
async function onDragAdd(event, objectType, targetIterationId) {
  const objectId = Number(event?.item?.dataset?.id)
  if (!objectId) return loadWorkbench()
  try {
    await moveWorkbenchItem({ object_type: objectType, object_id: objectId, target_iteration_id: targetIterationId })
    await loadWorkbench()
    ElMessage.success('已移动到目标迭代')
  } catch (error) {
    if (dragSnapshot.value) iterations.value = dragSnapshot.value
    ElMessageBox.alert(error?.response?.data?.detail || '移动失败', '提示', { type: 'warning' })
  }
}
async function activateRequirementRow(item) { try { await activateRequirement(item.id); await loadWorkbench(); ElMessage.success('需求已激活') } catch (error) { showActionError(error, '需求激活失败') } }
async function completeRequirementRow(item) { try { await completeRequirement(item.id); await loadWorkbench(); ElMessage.success('需求已完成') } catch (error) { showActionError(error, '需求完成失败') } }
function openRequirementClose(item) { selectedRequirement.value = item; Object.assign(closeForm, { reason: '', remark: '' }); closeRequirementVisible.value = true }
async function submitRequirementClose() { if (!closeForm.reason) return ElMessage.warning('请选择关闭原因'); saving.value = true; try { await closeRequirement(selectedRequirement.value.id, { ...closeForm }); closeRequirementVisible.value = false; await loadWorkbench(); ElMessage.success('需求已关闭') } catch (error) { showActionError(error, '需求关闭失败') } finally { saving.value = false } }
async function activateTaskRow(item) { try { await activateTask(item.id); await loadWorkbench(); ElMessage.success('任务已激活') } catch (error) { showActionError(error, '任务激活失败') } }
async function completeTaskRow(item) { try { await completeTask(item.id); await loadWorkbench(); ElMessage.success('任务已完成') } catch (error) { showActionError(error, '任务完成失败') } }
function openTaskClose(item) { selectedTask.value = item; Object.assign(closeForm, { reason: '', remark: '' }); closeTaskVisible.value = true }
async function submitTaskClose() { if (!closeForm.reason) return ElMessage.warning('请选择关闭原因'); saving.value = true; try { await closeTask(selectedTask.value.id, { ...closeForm }); closeTaskVisible.value = false; await loadWorkbench(); ElMessage.success('任务已关闭') } catch (error) { showActionError(error, '任务关闭失败') } finally { saving.value = false } }
function openBugAction(item, action) { selectedBug.value = item; bugActionType.value = action; Object.assign(bugActionForm, { iteration_id: item.iteration_id || null, resolution: '已解决', remark: '' }); bugActionVisible.value = true }
async function submitBugAction() {
  saving.value = true
  try {
    const actions = { start_fixing: startFixingBug, resolve: resolveBug, activate: activateBug, suspend: suspendBug, close: closeBug, verify_passed: verifyBugPassed, verify_failed: verifyBugFailed }
    const payload = ['activate', 'close'].includes(bugActionType.value) ? { remark: bugActionForm.remark } : { ...bugActionForm }
    await actions[bugActionType.value](selectedBug.value.id, payload)
    bugActionVisible.value = false
    await loadWorkbench()
    ElMessage.success('Bug 状态已更新')
  } catch (error) {
    showActionError(error, 'Bug 操作失败')
  } finally {
    saving.value = false
  }
}
function openCaseExecution(item) {
  selectedCase.value = item
  const steps = Array.isArray(item.steps_json) && item.steps_json.length ? item.steps_json : [{ step: item.title, expected: '' }]
  Object.assign(caseExecutionForm, {
    execute_time: defaultExecutionTime(),
    steps_result_json: steps.map((step) => ({ step: step.step || '', expected: step.expected || '', result: 'passed', actual: '' }))
  })
  caseExecutionVisible.value = true
}
function openCaseBug(item) {
  if (!canCreateBugFromCase(item)) return
  selectedCase.value = item
  Object.assign(caseBugForm, {
    title: item.title,
    bug_type: '代码错误',
    severity: '3',
    priority: '3',
    reproduce_steps: buildCaseReproduceText(item),
    actual_result: executionResultLabel(item.last_execute_result)
  })
  caseBugVisible.value = true
}
async function submitCaseExecution() {
  saving.value = true
  try {
    await executeTestCase(selectedCase.value.id, { ...caseExecutionForm })
    caseExecutionVisible.value = false
    await loadWorkbench()
    ElMessage.success('用例执行结果已保存')
  } finally {
    saving.value = false
  }
}
async function submitCaseBug() {
  if (!caseBugForm.title.trim()) return ElMessage.warning('请填写 Bug 标题')
  saving.value = true
  try {
    await createBugFromTestCase(selectedCase.value.id, { ...caseBugForm })
    caseBugVisible.value = false
    await loadWorkbench()
    ElMessage.success('Bug 已提交')
  } finally {
    saving.value = false
  }
}
function buildCaseReproduceText(item) {
  const steps = Array.isArray(item.steps_json) ? item.steps_json : []
  if (!steps.length) return item.title
  return [
    '[步骤]',
    ...steps.map((step, index) => `${index + 1}. ${step.step || ''}`),
    '',
    '[预期]',
    ...steps.map((step, index) => `${index + 1}. ${step.expected || ''}`),
    '',
    '[最近执行结果]',
    executionResultLabel(item.last_execute_result)
  ].join('\n')
}
function showActionError(error, fallback) {
  ElMessageBox.alert(error?.response?.data?.detail || fallback, '提示', { type: 'warning' })
}

onMounted(loadWorkbench)
</script>
