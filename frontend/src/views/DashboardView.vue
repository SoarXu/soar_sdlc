<template>
  <section class="workbench-page">
    <div class="page-head">
      <div>
        <h1>工作台</h1>
        <p>今日工作与项目进度</p>
      </div>
      <div class="page-actions">
        <div class="workbench-filter-toolbar">
          <el-input
            v-model="keywordFilter"
            clearable
            placeholder="搜索标题 / 项目"
            class="workbench-search"
          />
          <el-select
            v-model="projectFilter"
            multiple
            collapse-tags
            collapse-tags-tooltip
            clearable
            placeholder="项目"
            class="workbench-filter"
          >
            <el-option v-for="option in filterOptions.projects" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
          <el-select
            v-model="iterationFilter"
            multiple
            collapse-tags
            collapse-tags-tooltip
            clearable
            placeholder="迭代"
            class="workbench-filter"
          >
            <el-option v-for="option in filterOptions.iterations" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
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
          <el-select v-model="stateFilter" multiple collapse-tags collapse-tags-tooltip clearable placeholder="状态" class="workbench-filter">
            <el-option v-for="option in filterOptions.statuses" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
          <el-select v-model="priorityFilter" multiple collapse-tags collapse-tags-tooltip clearable placeholder="优先级" class="workbench-filter">
            <el-option v-for="option in filterOptions.priorities" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
          <el-select v-model="handlerFilter" multiple collapse-tags collapse-tags-tooltip clearable placeholder="当前处理人" class="workbench-filter">
            <el-option v-for="option in filterOptions.handlers" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </div>
        <div class="workbench-action-refresh">
          <el-button :loading="loading" @click="loadWorkbench">刷新</el-button>
        </div>
      </div>
    </div>

    <div v-loading="loading" class="workbench-list">
      <section class="workbench-list-section">
        <header class="workbench-list-section-head">
          <div>
            <h2>进行中迭代工作项</h2>
            <p>当前用户可见项目中的需求、任务和 Bug。</p>
          </div>
          <el-tag>{{ filteredListItems.length }} 项</el-tag>
        </header>

        <el-empty v-if="!filteredListItems.length" class="workbench-section-empty" description="暂无符合筛选条件的工作项" />

        <div v-else class="workbench-list-table">
          <el-table ref="workbenchTable" :data="pagedListItems" height="100%" border stripe :row-class-name="workbenchRowClassName" @selection-change="onWorkbenchSelectionChange">
            <el-table-column type="selection" width="48" :selectable="canSelectWorkbenchItemForBatchAssignment" />
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
              <template #default="{ row }">{{ ownerName(row.handler_id) }}</template>
            </el-table-column>
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <el-tag size="small" :type="itemStatusTag(row)" effect="light" :class="{ 'workbench-status-tag-terminal': isTerminalWorkItem(row) }">
                  {{ itemStatusLabel(row) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="优先级" width="110">
              <template #default="{ row }">
                <RequirementPriorityBadge v-if="row.priority || row.severity" :value="row.severity || row.priority" />
                <span v-else>-</span>
              </template>
            </el-table-column>
            <el-table-column label="截止日期" width="120">
              <template #default="{ row }">{{ row.due_date || '-' }}</template>
            </el-table-column>
            <el-table-column label="最近更新" width="180">
              <template #default="{ row }">{{ formatWorkbenchDateTime(row.update_time) }}</template>
            </el-table-column>
            <el-table-column label="操作" :width="workflowOperationWidth" fixed="right">
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
                    @command="handleWorkflowCommand(row, $event)"
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
          <div v-if="selectedWorkbenchItems.length" class="workbench-batch-assignment-footer">
            <BatchAssignmentBar
              :object-type="selectedWorkbenchObjectType"
              :project-id="selectedWorkbenchProjectId"
              :selected-rows="selectedWorkbenchItems"
              :users="users"
              @completed="onWorkbenchBatchAssignmentCompleted"
              @error="onWorkbenchBatchAssignmentError"
            />
          </div>
        </div>
        <footer class="workbench-pagination-footer">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="pagedListPage.total"
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="handleWorkbenchCurrentPageChange"
            @size-change="handleWorkbenchPageSizeChange"
          />
        </footer>
      </section>
    </div>

    <el-dialog v-model="caseExecutionVisible" :title="`执行用例 ${selectedCase?.title || ''}`" width="760px">
      <el-form label-position="top">
        <el-form-item label="执行时间">
          <el-date-picker v-model="caseExecutionForm.execute_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" />
        </el-form-item>
        <el-table :data="caseExecutionForm.steps_result_json" border>
          <el-table-column label="步骤" min-width="180"><template #default="{ row }"><div class="rich-text" v-html="safeExecutionCellHtml(row.step, row.rich_content)"></div></template></el-table-column>
          <el-table-column label="预期" min-width="180"><template #default="{ row }"><div class="rich-text" v-html="safeExecutionCellHtml(row.expected, row.rich_content)"></div></template></el-table-column>
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

    <RequirementEditDialog
      v-if="activeEditorType === 'requirement'"
      v-model="editorVisible"
      :item-id="activeEditorId"
      @saved="handleEditorSaved"
    />
    <TaskEditDialog
      v-if="activeEditorType === 'task'"
      v-model="editorVisible"
      :item-id="activeEditorId"
      @saved="handleEditorSaved"
    />
    <BugEditDialog
      v-if="activeEditorType === 'bug'"
      v-model="editorVisible"
      :item-id="activeEditorId"
      @saved="handleEditorSaved"
    />
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchWorkbench } from '../api/dashboard'
import { createBugFromTestCase, executeTestCase } from '../api/testCases'
import { fetchUsers } from '../api/users'
import { fetchWorkflowTransitionsBatch } from '../api/workflowRuntime'
import { workflowActionColumnWidth } from '../utils/workflowActionColumn'
import { resolveWorkbenchWorkflowCommand } from '../utils/workbenchWorkflowCommands'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import RichTextPasteEditor from '../components/RichTextPasteEditor.vue'
import WorkflowActionButtons from '../components/WorkflowActionButtons.vue'
import BatchAssignmentBar from '../components/BatchAssignmentBar.vue'
import BugEditDialog from '../components/work-items/BugEditDialog.vue'
import RequirementEditDialog from '../components/work-items/RequirementEditDialog.vue'
import TaskEditDialog from '../components/work-items/TaskEditDialog.vue'
import { showActionError } from '../utils/actionFeedback'
import {
  buildWorkbenchFilterOptions,
  executionResultLabel,
  filterWorkbenchItems,
  formatWorkbenchDateTime,
  isTerminalWorkItem,
  itemStatusLabel,
  itemStatusTag,
  paginateWorkbenchItems,
  shouldShowWorkbenchWorkflowActions,
  sortWorkbenchItems,
  typeLabel,
  typeTag,
  workbenchInlineActions
} from '../utils/workbenchViewModel'
import { DEFAULT_BUG_TYPE_KEY } from '../utils/bugTypeOptions'
import { useBugTypes } from '../utils/useBugTypes'
import { canSelectForBatchAssignment } from '../utils/batchAssignmentSelection'
import { safeExecutionCellHtml, testCaseExecutionRows } from '../utils/testCaseRichText'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const workbenchData = ref({})
const users = ref([])
const workflowTransitions = ref({})
const workbenchTable = ref(null)
const selectedWorkbenchItems = ref([])
const keywordFilter = ref('')
const projectFilter = ref([])
const iterationFilter = ref([])
const typeFilter = ref([])
const stateFilter = ref([])
const priorityFilter = ref([])
const handlerFilter = ref([])
const currentPage = ref(1)
const pageSize = ref(20)
const selectedCase = ref(null)
const caseExecutionVisible = ref(false)
const caseBugVisible = ref(false)
const editorVisible = ref(false)
const activeEditorType = ref('')
const activeEditorId = ref(null)
const caseExecutionForm = reactive({ execute_time: '', steps_result_json: [] })
const caseBugForm = reactive({ title: '', bug_type: DEFAULT_BUG_TYPE_KEY, severity: '3', priority: '3', reproduce_steps: '', actual_result: '' })

const itemTypes = [
  { label: '需求', value: 'requirement' },
  { label: '任务', value: 'task' },
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

const activeIterationItems = computed(() => workbenchData.value.active_iteration_items || [])
const filterOptions = computed(() => buildWorkbenchFilterOptions(activeIterationItems.value, users.value))
const filteredListItems = computed(() => sortWorkbenchItems(filterWorkbenchItems(activeIterationItems.value, activeFilters.value)))
const pagedListPage = computed(() => paginateWorkbenchItems(filteredListItems.value, currentPage.value, pageSize.value))
const pagedListItems = computed(() => pagedListPage.value.items)
const workflowOperationWidth = computed(() => workflowActionColumnWidth(
  filteredListItems.value.map((row) => workflowTransitionsFor(row)),
  { minWidth: 180, extraWidth: 90 }
))
const selectedWorkbenchObjectType = computed(() => selectedWorkbenchItems.value[0]?.object_type || '')
const selectedWorkbenchProjectId = computed(() => selectedWorkbenchItems.value[0]?.project_id || null)
const activeFilters = computed(() => ({
  keyword: keywordFilter.value,
  projectIds: projectFilter.value,
  iterationIds: iterationFilter.value,
  types: typeFilter.value,
  stateIds: stateFilter.value,
  priorities: priorityFilter.value,
  handlerIds: handlerFilter.value
}))

function ownerName(id) {
  return users.value.find((item) => item.id === id)?.full_name || '未分配'
}

function iterationLabel(id, name) {
  if (name) return name
  if (id) return `迭代 #${id}`
  return '-'
}

function inlineActionsFor(item) {
  return workbenchInlineActions('active_iteration', item)
}

function shouldShowWorkflowActions(item) {
  return shouldShowWorkbenchWorkflowActions('active_iteration', item)
}

function workflowTransitionsFor(item) {
  return workflowTransitions.value[`${item.object_type}:${item.id}`] || []
}

function workbenchBatchRow(item) {
  return { ...item, transitions: workflowTransitionsFor(item) }
}

function canSelectWorkbenchItemForBatchAssignment(item) {
  return canSelectForBatchAssignment(workbenchBatchRow(item), selectedWorkbenchItems.value)
}

function onWorkbenchSelectionChange(rows) {
  const firstRow = rows.find((row) => canSelectForBatchAssignment(workbenchBatchRow(row), []))
  const allowedRows = firstRow
    ? rows.filter((row) => (
      row.object_type === firstRow.object_type
      && row.project_id === firstRow.project_id
      && canSelectForBatchAssignment(workbenchBatchRow(row), [])
    ))
    : []
  selectedWorkbenchItems.value = allowedRows.map(workbenchBatchRow)
  if (allowedRows.length !== rows.length) nextTick(() => syncWorkbenchSelection(allowedRows))
}

function syncWorkbenchSelection(rows) {
  workbenchTable.value?.clearSelection()
  rows.forEach((row) => workbenchTable.value?.toggleRowSelection(row, true))
}

function clearWorkbenchSelection() {
  selectedWorkbenchItems.value = []
  workbenchTable.value?.clearSelection()
}

function resetWorkbenchPagination() {
  clearWorkbenchSelection()
  currentPage.value = 1
}

function handleWorkbenchCurrentPageChange(page) {
  clearWorkbenchSelection()
  currentPage.value = page
}

function handleWorkbenchPageSizeChange(size) {
  clearWorkbenchSelection()
  pageSize.value = size
  currentPage.value = 1
}

async function onWorkbenchBatchAssignmentCompleted() {
  clearWorkbenchSelection()
  await loadWorkbench()
}

function onWorkbenchBatchAssignmentError(error) {
  showActionError(error, '批量指派失败')
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

function defaultExecutionTime() {
  const date = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function runItemAction(item, action) {
  if (!action) return
  const handlers = {
    execute_case: openCaseExecution,
    create_case_bug: openCaseBug
  }
  handlers[action.key]?.(item)
}

function handleWorkflowCommand(item, { commandType }) {
  const command = resolveWorkbenchWorkflowCommand(item, commandType)
  if (!command) return
  activeEditorType.value = command.objectType
  activeEditorId.value = command.objectId
  editorVisible.value = true
}

async function handleEditorSaved() {
  editorVisible.value = false
  await loadWorkbench()
}

function openCaseExecution(item) {
  selectedCase.value = item
  Object.assign(caseExecutionForm, {
    execute_time: defaultExecutionTime(),
    steps_result_json: testCaseExecutionRows(item)
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
  const runtimeItems = (data.active_iteration_items || []).filter((item) => shouldShowWorkflowActions(item))
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
  clearWorkbenchSelection()
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
watch([
  keywordFilter,
  projectFilter,
  iterationFilter,
  typeFilter,
  stateFilter,
  priorityFilter,
  handlerFilter
], resetWorkbenchPagination, { deep: true })
watch(() => pagedListPage.value.page, (correctedPage) => {
  if (currentPage.value === correctedPage) return
  clearWorkbenchSelection()
  currentPage.value = correctedPage
})
</script>

<style scoped>
.workbench-filter-toolbar {
  display: grid;
  grid-template-columns: repeat(4, minmax(150px, 1fr));
  align-items: center;
  gap: 10px;
}

@media (max-width: 1200px) {
  .workbench-filter-toolbar {
    grid-template-columns: repeat(2, minmax(180px, 1fr));
  }
}

@media (max-width: 720px) {
  .workbench-filter-toolbar {
    grid-template-columns: 1fr;
  }
}

.workbench-batch-assignment-footer {
  position: static;
  flex: 0 0 auto;
  min-height: 48px;
  padding: 0 12px 8px;
  border-top: 1px solid var(--el-border-color-lighter);
  background: var(--el-bg-color);
}
</style>
