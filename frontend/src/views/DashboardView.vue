<template>
  <section class="workbench-page">
    <div class="page-head">
      <div>
        <h1>工作台</h1>
        <p>今日工作与项目进度</p>
      </div>
      <div class="page-actions">
        <div class="workbench-action-filters">
          <el-input
            v-model="keywordFilter"
            clearable
            placeholder="搜索标题 / 项目"
            class="workbench-search"
          />
          <el-select
            v-model="typeFilter"
            multiple
            collapse-tags
            collapse-tags-tooltip
            clearable
            placeholder="类型"
            class="workbench-filter"
          >
            <el-option v-for="type in itemTypes" :key="type.value" :label="type.label" :value="type.value" />
          </el-select>
        </div>
        <div class="workbench-action-refresh">
          <el-button :loading="loading" @click="loadWorkbench">刷新</el-button>
        </div>
      </div>
    </div>

    <div class="workbench-summary">
      <el-card v-for="card in viewModel.summaryCards" :key="card.key" shadow="never">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
      </el-card>
    </div>

    <el-radio-group v-model="activeView" class="workbench-entry-switch" size="large">
      <el-radio-button v-for="entry in viewModel.entryTabs" :key="entry.key" :label="entry.key">
        {{ entry.label }}
      </el-radio-button>
    </el-radio-group>

    <div v-if="activeView === 'following'" class="workbench-follow-tabs">
      <el-tabs v-model="activeTrackingTab">
        <el-tab-pane
          v-for="tab in viewModel.trackingTabs"
          :key="tab.key"
          :label="`${tab.label} (${tab.total})`"
          :name="tab.key"
        />
      </el-tabs>
    </div>

    <div v-if="activeView === 'exception_center'" class="exception-filter-toolbar">
      <el-select v-model="exceptionProjectFilter" multiple collapse-tags clearable placeholder="项目">
        <el-option v-for="option in exceptionProjectOptions" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>
      <el-select v-model="typeFilter" multiple collapse-tags clearable placeholder="对象类型">
        <el-option v-for="type in itemTypes" :key="type.value" :label="type.label" :value="type.value" />
      </el-select>
      <el-select v-model="exceptionPriorityFilter" multiple collapse-tags clearable placeholder="优先级">
        <el-option v-for="option in exceptionPriorityOptions" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>
      <el-select v-model="exceptionStatusFilter" multiple collapse-tags clearable placeholder="状态">
        <el-option v-for="option in exceptionStatusOptions" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>
      <el-select v-model="exceptionOwnerFilter" multiple collapse-tags clearable placeholder="负责人">
        <el-option v-for="option in ownerOptions" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>
      <el-select v-model="exceptionHandlerFilter" multiple collapse-tags clearable placeholder="当前处理人">
        <el-option v-for="option in ownerOptions" :key="option.value" :label="option.label" :value="option.value" />
      </el-select>
      <el-input-number v-model="exceptionMinOverdueHours" :min="0" :step="1" controls-position="right" />
      <span class="exception-filter-unit">最少逾期小时</span>
    </div>

    <div v-loading="loading" class="workbench-list">
      <section class="workbench-list-section">
        <header class="workbench-list-section-head">
          <div>
            <h2>{{ activeListSection.label }}</h2>
            <p>{{ activeListSection.description }}</p>
          </div>
          <el-tag>{{ filteredListItems.length }} 项</el-tag>
        </header>

        <el-empty v-if="!filteredListItems.length" class="workbench-section-empty" :description="`${activeListSection.label}暂无工作项`" />

        <div v-else class="workbench-list-table">
          <el-table :data="filteredListItems" border stripe :row-class-name="workbenchRowClassName">
            <el-table-column prop="id" label="ID" width="90" />
            <el-table-column label="类型" width="100">
              <template #default="{ row }">
                <el-tag size="small" :type="typeTag(row.object_type)">{{ typeLabel(row.object_type) }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="标题" min-width="240" show-overflow-tooltip>
              <template #default="{ row }">
                <el-button
                  link
                  type="primary"
                  class="workbench-title-button"
                  :class="{ 'is-terminal': isTerminalWorkItem(row) }"
                  @click="openWorkItemDetail(row)"
                >
                  {{ row.title }}
                </el-button>
              </template>
            </el-table-column>
            <el-table-column prop="project_name" label="项目" min-width="140" show-overflow-tooltip />
            <el-table-column label="迭代" min-width="140" show-overflow-tooltip>
              <template #default="{ row }">{{ iterationLabel(row.iteration_id, row.iteration_name) }}</template>
            </el-table-column>
            <el-table-column label="当前处理人" width="130">
              <template #default="{ row }">{{ ownerName(row.owner_id) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag size="small" :type="itemStatusTag(row)" effect="light" :class="{ 'workbench-status-tag-terminal': isTerminalWorkItem(row) }">
                  {{ itemStatusLabel(row) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="优先级 / 结果" width="130">
              <template #default="{ row }">
                <RequirementPriorityBadge v-if="row.priority || row.severity" :value="row.severity || row.priority" />
                <span v-else>{{ executionResultLabel(row.last_execute_result) }}</span>
              </template>
            </el-table-column>
            <el-table-column :label="extraInfoLabel" min-width="170" show-overflow-tooltip>
              <template #default="{ row }">{{ extraInfo(row) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="180" fixed="right">
              <template #default="{ row }">
                <div class="workbench-list-actions">
                  <WorkflowActionButtons
                    v-if="shouldShowWorkflowActions(row)"
                    :object-type="row.object_type"
                    :object-id="row.id"
                    mode="list"
                    :transitions="workflowTransitionsFor(row)"
                    :auto-load="false"
                    :users="users"
                    @executed="loadWorkbench"
                  />
                  <el-button
                    v-for="action in inlineActionsFor(row)"
                    :key="action.key"
                    link
                    :type="action.type"
                    class="workbench-action-main"
                    @click="runItemAction(row, action)"
                  >
                    {{ action.label }}
                  </el-button>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </section>
    </div>

    <el-dialog v-model="caseExecutionVisible" :title="`执行用例 ${selectedCase?.title || ''}`" width="760px">
      <el-form label-position="top">
        <el-form-item label="执行时间">
          <el-date-picker v-model="caseExecutionForm.execute_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" />
        </el-form-item>
        <el-table :data="caseExecutionForm.steps_result_json" border>
          <el-table-column prop="step" label="步骤" min-width="180" />
          <el-table-column prop="expected" label="预期" min-width="180" />
          <el-table-column label="测试结果" width="140">
            <template #default="{ row }">
              <el-select v-model="row.result">
                <el-option v-for="option in executionResultOptions" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
            </template>
          </el-table-column>
          <el-table-column label="实际情况" min-width="180">
            <template #default="{ row }"><el-input v-model="row.actual" type="textarea" :rows="1" /></template>
          </el-table-column>
        </el-table>
      </el-form>
      <template #footer>
        <el-button @click="caseExecutionVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCaseExecution">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="caseBugVisible" title="提交 Bug" width="620px">
      <el-form label-position="top">
        <el-form-item label="Bug 标题" required><el-input v-model="caseBugForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="Bug 类型">
            <el-select v-model="caseBugForm.bug_type">
              <el-option v-for="option in bugTypeOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item label="严重程度">
            <el-select v-model="caseBugForm.severity">
              <el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="重现步骤"><RichTextPasteEditor v-model="caseBugForm.reproduce_steps" /></el-form-item>
        <el-form-item label="实际结果"><el-input v-model="caseBugForm.actual_result" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="caseBugVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitCaseBug">提交</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchWorkbench } from '../api/dashboard'
import { createBugFromTestCase, executeTestCase } from '../api/testCases'
import { fetchUsers } from '../api/users'
import { fetchWorkflowTransitionsBatch } from '../api/workflowRuntime'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import RichTextPasteEditor from '../components/RichTextPasteEditor.vue'
import WorkflowActionButtons from '../components/WorkflowActionButtons.vue'
import { showActionError } from '../utils/actionFeedback'
import {
  buildWorkbenchViewModel,
  executionResultLabel,
  filterWorkbenchItems,
  formatWorkbenchDateTime,
  isTerminalWorkItem,
  itemStatusLabel,
  itemStatusTag,
  shouldShowWorkbenchWorkflowActions,
  typeLabel,
  typeTag,
  workbenchInlineActions,
  workbenchMetaText
} from '../utils/workbenchViewModel'
import { DEFAULT_BUG_TYPE_KEY } from '../utils/bugTypeOptions'
import { useBugTypes } from '../utils/useBugTypes'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const workbenchData = ref({})
const users = ref([])
const workflowTransitions = ref({})
const activeView = ref('pending_handling')
const activeTrackingTab = ref('created_by_me')
const keywordFilter = ref('')
const typeFilter = ref([])
const exceptionProjectFilter = ref([])
const exceptionPriorityFilter = ref([])
const exceptionStatusFilter = ref([])
const exceptionOwnerFilter = ref([])
const exceptionHandlerFilter = ref([])
const exceptionMinOverdueHours = ref(0)
const selectedCase = ref(null)
const caseExecutionVisible = ref(false)
const caseBugVisible = ref(false)
const caseExecutionForm = reactive({ execute_time: '', steps_result_json: [] })
const caseBugForm = reactive({ title: '', bug_type: DEFAULT_BUG_TYPE_KEY, severity: '3', priority: '3', reproduce_steps: '', actual_result: '' })

const itemTypes = [
  { label: '需求', value: 'requirement' },
  { label: '任务', value: 'task' },
  { label: '测试用例', value: 'test_case' },
  { label: '测试单', value: 'test_run' },
  { label: 'Bug', value: 'bug' }
]

const executionResultOptions = [
  { label: '忽略', value: 'ignored' },
  { label: '通过', value: 'passed' },
  { label: '失败', value: 'failed' },
  { label: '阻塞', value: 'blocked' }
]

const { bugTypeOptions } = useBugTypes()
const priorityLevelOptions = [
  { label: '1级', value: '1' },
  { label: '2级', value: '2' },
  { label: '3级', value: '3' },
  { label: '4级', value: '4' },
  { label: '5级', value: '5' }
]

const viewModel = computed(() => buildWorkbenchViewModel(workbenchData.value))
const activeListSection = computed(() => (
  activeView.value === 'following'
    ? viewModel.value.trackingTabsByKey[activeTrackingTab.value]
    : viewModel.value.queueSectionsByKey[activeView.value]
))
const filteredListItems = computed(() => filterWorkbenchItems(activeListSection.value?.items || [], activeFilters.value))
const activeFilters = computed(() => ({
  keyword: keywordFilter.value,
  types: typeFilter.value,
  ...(activeView.value === 'exception_center' ? {
    projectIds: exceptionProjectFilter.value,
    priorities: exceptionPriorityFilter.value,
    stateIds: exceptionStatusFilter.value,
    ownerIds: exceptionOwnerFilter.value,
    handlerIds: exceptionHandlerFilter.value,
    minOverdueHours: exceptionMinOverdueHours.value
  } : {})
}))
const ownerOptions = computed(() => viewModel.value.owners.map((item) => ({ label: item.full_name, value: item.id })))
const exceptionItems = computed(() => viewModel.value.queueSectionsByKey.exception_center?.items || [])
const exceptionProjectOptions = computed(() => uniqueOptions(exceptionItems.value, 'project_id', 'project_name'))
const exceptionPriorityOptions = computed(() => uniqueOptions(
  exceptionItems.value.map((item) => ({ ...item, normalized_priority: item.priority || item.severity })),
  'normalized_priority',
  'normalized_priority'
))
const exceptionStatusOptions = computed(() => {
  const seen = new Map()
  for (const item of exceptionItems.value) {
    if (item.current_state_id && !seen.has(item.current_state_id)) {
      seen.set(item.current_state_id, itemStatusLabel(item))
    }
  }
  return [...seen].map(([value, label]) => ({ value, label }))
})
const extraInfoLabel = computed(() => {
  if (activeListSection.value?.key === 'exception_center') return '异常说明'
  if (['watched_by_me', 'mentioned_me'].includes(activeListSection.value?.key)) return '来源'
  return '附加信息'
})

function ownerName(id) {
  return users.value.find((item) => item.id === id)?.full_name || '未分配'
}

function iterationLabel(id, name) {
  if (name) return name
  if (id) return `迭代 #${id}`
  return '-'
}

function extraInfo(item) {
  const meta = workbenchMetaText(activeListSection.value?.key, item)
  if (meta) return meta
  if (item.object_type === 'test_case' && item.last_execute_time) return formatWorkbenchDateTime(item.last_execute_time)
  return '-'
}

function inlineActionsFor(item) {
  return workbenchInlineActions(activeListSection.value?.key, item)
}

function shouldShowWorkflowActions(item, sectionKey = activeListSection.value?.key) {
  return shouldShowWorkbenchWorkflowActions(sectionKey, item)
}

function workflowTransitionsFor(item) {
  return workflowTransitions.value[`${item.object_type}:${item.id}`] || []
}

function workbenchRowClassName({ row }) {
  return isTerminalWorkItem(row) ? 'workbench-row-terminal' : ''
}

function openWorkItemDetail(item) {
  router.push(detailLink(item))
}

function detailLink(item) {
  if (item.object_type === 'requirement') return { name: 'requirement-detail', params: { id: item.id }, query: { from: 'dashboard' } }
  if (item.object_type === 'task') return { name: 'task-detail', params: { id: item.id }, query: { from: 'dashboard' } }
  if (item.object_type === 'test_case') return { name: 'test-case-detail', params: { id: item.id }, query: { from: 'dashboard' } }
  if (item.object_type === 'test_run') return { name: 'tests', query: { run_id: item.id, from: 'dashboard' } }
  return { name: 'bug-detail', params: { id: item.id }, query: { from: 'dashboard' } }
}

function uniqueOptions(items, valueKey, labelKey, fallbackLabel) {
  const seen = new Map()
  for (const item of items) {
    const value = item[valueKey]
    if (value === null || value === undefined || value === '') continue
    if (!seen.has(value)) seen.set(value, item[labelKey] || fallbackLabel || String(value))
  }
  return [...seen].map(([value, label]) => ({ value, label }))
}

function defaultExecutionTime() {
  const date = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function normalizeCaseSteps(value) {
  return Array.isArray(value) && value.length
    ? value.map((item) => ({ step: item.step || '', expected: item.expected || '' }))
    : [{ step: '', expected: '' }]
}

function runItemAction(item, action) {
  if (!action) return
  const handlers = {
    execute_case: openCaseExecution,
    create_case_bug: openCaseBug
  }
  handlers[action.key]?.(item)
}

function openCaseExecution(item) {
  selectedCase.value = item
  const steps = normalizeCaseSteps(item.steps_json)
  Object.assign(caseExecutionForm, {
    execute_time: defaultExecutionTime(),
    steps_result_json: steps.map((step) => ({ step: step.step, expected: step.expected, result: 'passed', actual: '' }))
  })
  caseExecutionVisible.value = true
}

function openCaseBug(item) {
  selectedCase.value = item
  Object.assign(caseBugForm, {
    title: item.title || '',
    bug_type: DEFAULT_BUG_TYPE_KEY,
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
    await executeTestCase(selectedCase.value.id, {
      execute_time: caseExecutionForm.execute_time,
      steps_result_json: caseExecutionForm.steps_result_json
    })
    caseExecutionVisible.value = false
    await loadWorkbench()
    ElMessage.success('用例执行结果已保存')
  } catch (error) {
    showActionError(error, '用例执行结果保存失败')
  } finally {
    saving.value = false
  }
}

async function submitCaseBug() {
  if (!caseBugForm.title.trim()) {
    ElMessage.warning('请填写 Bug 标题')
    return
  }
  saving.value = true
  try {
    await createBugFromTestCase(selectedCase.value.id, { ...caseBugForm })
    caseBugVisible.value = false
    await loadWorkbench()
    ElMessage.success('Bug 已提交')
  } catch (error) {
    showActionError(error, 'Bug 提交失败')
  } finally {
    saving.value = false
  }
}

function buildCaseReproduceText(item) {
  const steps = Array.isArray(item.steps_json) ? item.steps_json : []
  if (!steps.length) return item.title || ''
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

async function loadWorkflowTransitions(data) {
  const sections = [
    ['pending_handling', data.pending_handling?.items || []],
    ['unassigned', data.unassigned?.items || []],
    ['created_by_me', data.created_by_me?.items || []],
    ['watched_by_me', data.watched_by_me?.items || []],
    ['mentioned_me', data.mentioned_me?.items || []],
    ['exception_center', data.exception_center?.items || []]
  ]
  const runtimeItems = sections.flatMap(([sectionKey, items]) => (
    items.filter((item) => shouldShowWorkflowActions(item, sectionKey))
  ))
  const uniqueItems = [...new Map(runtimeItems.map((item) => [`${item.object_type}:${item.id}`, item])).values()]
  if (!uniqueItems.length) {
    workflowTransitions.value = {}
    return
  }
  try {
    const { data: response } = await fetchWorkflowTransitionsBatch(
      uniqueItems.map((item) => ({ object_type: item.object_type, id: item.id }))
    )
    workflowTransitions.value = Object.fromEntries(
      (response.items || []).map((item) => [`${item.object_type}:${item.id}`, item.transitions || []])
    )
  } catch {
    workflowTransitions.value = {}
  }
}

async function loadWorkbench() {
  loading.value = true
  try {
    const [workbenchResponse, usersResponse] = await Promise.all([
      fetchWorkbench(),
      fetchUsers()
    ])
    workbenchData.value = workbenchResponse.data || {}
    users.value = usersResponse.data || []
    await loadWorkflowTransitions(workbenchResponse.data || {})
  } catch (error) {
    showActionError(error, '工作台加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadWorkbench)
</script>

<style scoped>
.exception-filter-toolbar {
  display: grid;
  grid-template-columns: repeat(6, minmax(140px, 1fr)) 150px auto;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}

.exception-filter-unit {
  color: #5f6b7a;
  white-space: nowrap;
}
</style>
