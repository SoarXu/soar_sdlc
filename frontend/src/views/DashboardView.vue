<template>
  <section class="workbench-page" :class="{ 'workbench-page-board': displayMode === 'board' }">
    <div class="page-head">
      <div>
        <h1>工作台</h1>
        <p>按迭代和负责人聚合当前需要处理的需求、任务、测试用例和 Bug。</p>
      </div>
      <div class="workbench-view-switch">
        <span>工作视图</span>
        <el-radio-group v-model="viewMode" size="small">
          <el-radio-button label="mine">我的</el-radio-button>
          <el-radio-button label="all">全部</el-radio-button>
        </el-radio-group>
      </div>
      <div class="page-actions">
        <div class="workbench-action-filters">
          <el-select v-model="iterationFilter" multiple collapse-tags collapse-tags-tooltip clearable filterable placeholder="迭代" class="workbench-filter wide">
            <el-option v-for="iteration in iterations" :key="iteration.id" :label="iteration.name" :value="iteration.id" />
          </el-select>
          <el-select v-if="viewMode === 'all'" v-model="ownerFilter" clearable filterable placeholder="负责人" class="workbench-filter">
            <el-option v-for="owner in owners" :key="owner.id" :label="owner.full_name" :value="owner.id" />
          </el-select>
          <el-select v-model="typeFilter" clearable placeholder="类型" class="workbench-filter">
            <el-option v-for="type in itemTypes" :key="type.value" :label="type.label" :value="type.value" />
          </el-select>
          <el-input v-model="keywordFilter" clearable placeholder="搜索标题/项目" class="workbench-search" />
          <el-checkbox v-model="hideEmptyIterations" class="workbench-checkbox">仅显示有工作项</el-checkbox>
        </div>
        <div class="workbench-action-refresh">
          <el-button :loading="loading" @click="loadWorkbench">刷新</el-button>
        </div>
      </div>
    </div>

    <div class="workbench-summary">
      <el-card v-for="item in summaryCards" :key="item.key" shadow="never">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </el-card>
    </div>

    <el-radio-group v-model="displayMode" class="workbench-mode" size="large">
      <el-radio-button label="list">列表</el-radio-button>
      <el-radio-button label="board">看板</el-radio-button>
      <el-radio-button label="stats">统计</el-radio-button>
    </el-radio-group>

    <el-empty v-if="!loading && !filteredIterations.length" class="workbench-empty" :description="emptyDescription" />

    <div v-else-if="displayMode === 'list'" v-loading="loading" class="workbench-list">
      <section v-for="section in listSections" :key="section.key" class="workbench-list-section">
        <header class="workbench-list-section-head">
          <div>
            <h2>{{ section.label }}</h2>
            <p>{{ section.description }}</p>
          </div>
          <el-tag :type="section.tagType || undefined">{{ section.items.length }} 项</el-tag>
        </header>
        <div v-if="section.items.length" class="workbench-list-table">
          <el-table :data="section.items" border stripe height="100%">
            <el-table-column label="类型" width="100">
              <template #default="{ row }"><el-tag size="small" :type="typeTag(row.object_type)">{{ typeLabel(row.object_type) }}</el-tag></template>
            </el-table-column>
            <el-table-column label="标题" min-width="220" show-overflow-tooltip>
              <template #default="{ row }">
                <el-button link type="primary" class="workbench-title-button" @click="openWorkItemDrawer(row)">{{ row.title }}</el-button>
              </template>
            </el-table-column>
            <el-table-column prop="project_name" label="项目" min-width="140" show-overflow-tooltip />
            <el-table-column prop="iteration_name" label="迭代" min-width="120" show-overflow-tooltip />
            <el-table-column label="负责人" width="120"><template #default="{ row }">{{ ownerName(row.owner_id) }}</template></el-table-column>
            <el-table-column label="状态" width="110"><template #default="{ row }">{{ itemStatusLabel(row) }}</template></el-table-column>
            <el-table-column label="优先级/结果" width="120">
              <template #default="{ row }">
                <RequirementPriorityBadge v-if="row.priority || row.severity" :value="row.severity || row.priority" />
                <span v-else>{{ executionResultLabel(row.last_execute_result) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="100" fixed="right">
              <template #default="{ row }"><el-button link type="primary" @click="openWorkItemDrawer(row)">处理</el-button></template>
            </el-table-column>
          </el-table>
        </div>
        <el-empty v-else class="workbench-section-empty" :description="`${section.label}暂无工作项`" />
      </section>
    </div>

    <div v-else-if="displayMode === 'stats'" v-loading="loading" class="workbench-stats">
      <el-table :data="projectStatsRows" border stripe row-key="id" default-expand-all>
        <el-table-column prop="name" label="项目 / 迭代" min-width="220" />
        <el-table-column prop="iteration_total" label="迭代数" width="100">
          <template #default="{ row }">{{ row.type === 'project' ? row.iteration_total : '-' }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">{{ row.type === 'iteration' ? iterationStatusLabel(row.status) : '-' }}</template>
        </el-table-column>
        <el-table-column prop="requirements" label="需求" width="90" />
        <el-table-column prop="tasks" label="任务" width="90" />
        <el-table-column prop="test_cases" label="用例" width="90" />
        <el-table-column prop="bugs" label="Bug" width="90" />
        <el-table-column prop="total" label="合计" width="90" />
      </el-table>
    </div>

    <div v-else v-loading="loading" class="workbench-board-wrap">
      <el-empty v-if="!boardColumns.length" class="workbench-empty" description="当前筛选下暂无迭代" />

      <div v-else class="workbench-board">
        <section v-for="column in boardColumns" :key="column.key" class="workbench-project-column">
          <header class="workbench-project-column-head">
            <div>
              <h2>{{ column.title }}</h2>
              <p>{{ column.iterations.length }} 个迭代</p>
            </div>
            <el-tag>{{ column.total }} 项</el-tag>
          </header>
          <div class="workbench-project-column-list">
            <article v-for="iteration in column.iterations" :key="`${column.key}-${iteration.id}`" class="iteration-board">
              <header class="iteration-board-head">
                <div>
                  <h2>{{ iteration.name }}</h2>
                  <span>{{ iterationStatusLabel(iteration.status) }} · {{ iteration.start_date || '-' }} 至 {{ iteration.end_date || '-' }}</span>
                  <div class="iteration-project-scope">
                    <span>关联项目</span>
                    <el-tag v-for="project in iteration.projects || []" :key="project.id" size="small" effect="plain">
                      {{ project.name }}
                    </el-tag>
                    <el-tag v-if="!(iteration.projects || []).length" size="small" type="info" effect="plain">未绑定项目</el-tag>
                  </div>
                </div>
                <div class="iteration-board-tools">
                  <el-tag>{{ boardTotal(iteration) }} 项</el-tag>
                  <el-button link type="primary" @click="toggleIteration(iteration.context_key)">
                    {{ isIterationExpanded(iteration.context_key) ? '收起' : '展开' }}
                  </el-button>
                </div>
              </header>

              <div v-if="isIterationExpanded(iteration.context_key)" class="workbench-lanes">
                <section v-for="group in visibleGroups(iteration)" :key="`${iteration.id}-${group.key}`" class="workbench-lane">
                  <header>
                    <span>{{ group.label }}</span>
                    <strong>{{ group.items.length }}</strong>
                  </header>
                  <VueDraggable
                    v-model="group.items"
                    class="workbench-card-list"
                    :group="{ name: 'workbench-items' }"
                    item-key="drag_key"
                    ghost-class="workbench-card-ghost"
                    chosen-class="workbench-card-chosen"
                    @start="onDragStart"
                    @add="(event) => onDragAdd(event, iteration.id)"
                  >
                    <div
                      v-for="item in visibleLaneItems(iteration.context_key, group.key, group.items)"
                      :key="item.drag_key"
                      class="workbench-card workbench-mini-card"
                      :class="`workbench-card-${item.object_type}`"
                      :data-id="item.id"
                      :data-type="item.object_type"
                    >
                      <div class="workbench-card-top">
                        <span class="workbench-type-dot" :class="`type-${item.object_type}`">{{ typeShortLabel(item.object_type) }}</span>
                        <button class="workbench-title workbench-card-button" type="button" @click="openWorkItemDrawer(item, iteration)">{{ item.title }}</button>
                        <span class="workbench-status">{{ itemStatusLabel(item) }}</span>
                      </div>
                      <div class="workbench-meta">
                        <span class="owner-chip">{{ ownerName(item.owner_id) }}</span>
                        <span class="workbench-project-name">{{ item.project_name || '-' }}</span>
                        <RequirementPriorityBadge v-if="item.priority || item.severity" :value="item.severity || item.priority" />
                      </div>
                    </div>
                  </VueDraggable>
                  <el-button
                    v-if="hasHiddenLaneItems(iteration.context_key, group.key, group.items)"
                    class="workbench-more"
                    link
                    type="primary"
                    @click="showMoreLaneItems(iteration.context_key, group.key)"
                  >
                    显示更多 {{ hiddenLaneCount(iteration.context_key, group.key, group.items) }} 项
                  </el-button>
                </section>
              </div>
              <button v-else class="iteration-collapsed-summary" type="button" @click="toggleIteration(iteration.context_key)">
                展开查看 {{ boardTotal(iteration) }} 个工作项
              </button>
            </article>
          </div>
        </section>
      </div>
    </div>

    <el-drawer v-model="workItemDrawerVisible" title="工作项处理" size="420px">
      <template v-if="selectedWorkItem">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="类型">{{ typeLabel(selectedWorkItem.object_type) }}</el-descriptions-item>
          <el-descriptions-item label="标题">{{ selectedWorkItem.title }}</el-descriptions-item>
          <el-descriptions-item label="项目">{{ selectedWorkItem.project_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="迭代">{{ selectedWorkItem.iteration_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="负责人">{{ ownerName(selectedWorkItem.owner_id) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ itemStatusLabel(selectedWorkItem) }}</el-descriptions-item>
        </el-descriptions>
        <div class="workbench-drawer-actions">
          <router-link :to="detailLink(selectedWorkItem)">
            <el-button type="primary">查看详情</el-button>
          </router-link>
          <template v-if="selectedWorkItem.object_type === 'requirement'">
            <el-button v-if="['draft', 'closed'].includes(selectedWorkItem.status)" type="warning" @click="activateRequirementRow(selectedWorkItem)">激活</el-button>
            <el-button v-if="selectedWorkItem.status === 'active'" type="success" @click="completeRequirementRow(selectedWorkItem)">完成</el-button>
            <el-button v-if="selectedWorkItem.status === 'active'" type="danger" @click="openRequirementClose(selectedWorkItem)">关闭</el-button>
          </template>
          <template v-else-if="selectedWorkItem.object_type === 'task'">
            <el-button v-if="['todo', 'closed'].includes(selectedWorkItem.status)" type="warning" @click="activateTaskRow(selectedWorkItem)">激活</el-button>
            <el-button v-if="selectedWorkItem.status === 'doing'" type="success" @click="completeTaskRow(selectedWorkItem)">完成</el-button>
            <el-button v-if="selectedWorkItem.status !== 'closed'" type="danger" @click="openTaskClose(selectedWorkItem)">关闭</el-button>
          </template>
          <template v-else-if="selectedWorkItem.object_type === 'test_case'">
            <el-button type="success" @click="openCaseExecution(selectedWorkItem)">执行</el-button>
            <el-button type="warning" :disabled="!canCreateBugFromCase(selectedWorkItem)" @click="openCaseBug(selectedWorkItem)">提 Bug</el-button>
          </template>
          <template v-else-if="selectedWorkItem.object_type === 'bug'">
            <el-button v-if="['open', 'reopened', 'suspended'].includes(selectedWorkItem.status)" type="success" @click="openBugAction(selectedWorkItem, 'start_fixing')">确认</el-button>
            <el-button v-if="selectedWorkItem.status === 'fixing'" type="success" @click="openBugAction(selectedWorkItem, 'resolve')">解决</el-button>
            <el-button v-if="selectedWorkItem.status === 'verifying'" type="success" @click="openBugAction(selectedWorkItem, 'verify_passed')">验证通过</el-button>
            <el-button v-if="selectedWorkItem.status === 'verifying'" type="danger" @click="openBugAction(selectedWorkItem, 'verify_failed')">验证失败</el-button>
            <el-button v-if="['verifying', 'closed'].includes(selectedWorkItem.status)" type="warning" @click="openBugAction(selectedWorkItem, 'activate')">激活</el-button>
            <el-button v-if="['open', 'fixing', 'reopened'].includes(selectedWorkItem.status)" type="warning" @click="openBugAction(selectedWorkItem, 'suspend')">挂起</el-button>
            <el-button v-if="['open', 'suspended', 'verifying'].includes(selectedWorkItem.status)" type="danger" @click="openBugAction(selectedWorkItem, 'close')">关闭</el-button>
          </template>
        </div>
      </template>
    </el-drawer>

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
        <el-form-item label="重现步骤"><RichTextPasteEditor v-model="caseBugForm.reproduce_steps" /></el-form-item>
        <el-form-item label="实际结果"><el-input v-model="caseBugForm.actual_result" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="caseBugVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitCaseBug">提交</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { VueDraggable } from 'vue-draggable-plus'
import { ElMessage, ElMessageBox } from 'element-plus'

import { fetchWorkbench, moveWorkbenchItem } from '../api/dashboard'
import { activateRequirement, closeRequirement, completeRequirement } from '../api/requirements'
import { activateTask, closeTask, completeTask } from '../api/tasks'
import { createBugFromTestCase, executeTestCase } from '../api/testCases'
import { activateBug, closeBug, resolveBug, startFixingBug, suspendBug, verifyBugFailed, verifyBugPassed } from '../api/bugs'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import RichTextPasteEditor from '../components/RichTextPasteEditor.vue'

const loading = ref(false)
const saving = ref(false)
const router = useRouter()
const iterations = ref([])
const owners = ref([])
const reviewTasks = ref([])
const viewMode = ref('mine')
const displayMode = ref('list')
const iterationFilter = ref([])
const ownerFilter = ref(null)
const typeFilter = ref('')
const keywordFilter = ref('')
const hideEmptyIterations = ref(false)
const expandedIterationIds = ref(new Set())
const laneLimits = reactive({})
const dragSnapshot = ref(null)
const selectedWorkItem = ref(null)
const selectedRequirement = ref(null)
const selectedTask = ref(null)
const selectedBug = ref(null)
const selectedCase = ref(null)
const workItemDrawerVisible = ref(false)
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
  { label: 'Bug', value: 'bug' },
  { label: 'Code Review', value: 'code_review' }
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
const INITIAL_LANE_LIMIT = 8
const LANE_LIMIT_STEP = 8

const currentUserId = computed(() => {
  const storedId = Number(localStorage.getItem('current_user_id'))
  if (storedId) return storedId
  const username = localStorage.getItem('current_username') || ''
  const fullName = localStorage.getItem('current_full_name') || ''
  const user = owners.value.find((item) => item.username === username || item.full_name === fullName)
  return user?.id || null
})

const filteredIterations = computed(() => iterations.value
  .filter((iteration) => !iterationFilter.value.length || iterationFilter.value.includes(iteration.id))
  .map((iteration) => ({
    ...iteration,
    requirements: filterItems(iteration.requirements || []),
    tasks: filterItems(iteration.tasks || []),
    test_cases: filterItems(iteration.test_cases || []),
    bugs: filterItems(iteration.bugs || [])
  }))
  .filter((iteration) => !hideEmptyIterations.value || boardTotal(iteration) > 0)
  .sort(compareIterationsForWorkbench))

const summaryCards = computed(() => {
  const boards = filteredIterations.value
  return [
    { key: 'iterations', label: '迭代板块', value: boards.length },
    { key: 'requirements', label: '需求', value: boards.reduce((sum, item) => sum + item.requirements.length, 0) },
    { key: 'tasks', label: '任务', value: boards.reduce((sum, item) => sum + item.tasks.length, 0) },
    { key: 'test_cases', label: '测试用例', value: boards.reduce((sum, item) => sum + item.test_cases.length, 0) },
    { key: 'bugs', label: 'Bug', value: boards.reduce((sum, item) => sum + item.bugs.length, 0) },
    { key: 'code_review', label: 'Code Review', value: filteredReviewTasks.value.length }
  ]
})

const filteredReviewTasks = computed(() => {
  const keyword = keywordFilter.value.trim().toLowerCase()
  const effectiveOwnerId = viewMode.value === 'mine' ? currentUserId.value : ownerFilter.value
  return reviewTasks.value
    .filter((item) => viewMode.value !== 'mine' || Boolean(effectiveOwnerId))
    .filter((item) => !effectiveOwnerId || item.owner_id === effectiveOwnerId)
    .filter((item) => !keyword || `${item.title || ''} ${item.short_sha || ''} ${item.branch_name || ''}`.toLowerCase().includes(keyword))
})
const flatWorkbenchItems = computed(() => filteredIterations.value.flatMap((iteration) => [
  ...(iteration.requirements || []).map((item) => decorateListItem(item, iteration)),
  ...(iteration.tasks || []).map((item) => decorateListItem(item, iteration)),
  ...(iteration.test_cases || []).map((item) => decorateListItem(item, iteration)),
  ...(iteration.bugs || []).map((item) => decorateListItem(item, iteration))
]).sort((a, b) => {
  if (a.iteration_id !== b.iteration_id) return (b.iteration_id || 0) - (a.iteration_id || 0)
  return b.id - a.id
}))

const listSections = computed(() => [
  { key: 'requirement', label: typeLabel('requirement'), description: '按迭代汇总需要推进的需求', tagType: '', items: flatWorkbenchItems.value.filter((item) => item.object_type === 'requirement') },
  { key: 'task', label: typeLabel('task'), description: '按迭代汇总需要执行的任务', tagType: 'success', items: flatWorkbenchItems.value.filter((item) => item.object_type === 'task') },
  { key: 'test_case', label: typeLabel('test_case'), description: '按迭代汇总需要执行的测试用例', tagType: 'warning', items: flatWorkbenchItems.value.filter((item) => item.object_type === 'test_case') },
  { key: 'bug', label: typeLabel('bug'), description: '按迭代汇总需要处理的 Bug', tagType: 'danger', items: flatWorkbenchItems.value.filter((item) => item.object_type === 'bug') },
  { key: 'code_review', label: typeLabel('code_review'), description: '需要完成代码评审的提交', tagType: 'info', items: filteredReviewTasks.value }
].filter((section) => !typeFilter.value || section.key === typeFilter.value))

const boardColumns = computed(() => {
  const columns = new Map()
  for (const iteration of filteredIterations.value) {
    const projects = iteration.projects?.length ? iteration.projects : [{ id: 'unbound', name: '未绑定项目' }]
    for (const project of projects) {
      const key = `project-${project.id}`
      if (!columns.has(key)) {
        columns.set(key, {
          key,
          title: project.name,
          projectId: project.id,
          iterations: []
        })
      }
      columns.get(key).iterations.push(iterationForProjectColumn(iteration, project, key))
    }
  }
  return [...columns.values()]
    .sort((a, b) => {
      if (a.projectId === 'unbound') return 1
      if (b.projectId === 'unbound') return -1
      return a.title.localeCompare(b.title, 'zh-Hans-CN')
    })
    .map((column) => {
      const iterations = sortIterationsForBoard(column.iterations)
      return {
        ...column,
        iterations,
        total: iterations.reduce((sum, iteration) => sum + boardTotal(iteration), 0)
      }
    })
})

const projectStatsRows = computed(() => boardColumns.value.map((column) => ({
  id: column.key,
  type: 'project',
  name: column.title,
  iteration_total: column.iterations.length,
  requirements: column.iterations.reduce((sum, iteration) => sum + (iteration.requirements?.length || 0), 0),
  tasks: column.iterations.reduce((sum, iteration) => sum + (iteration.tasks?.length || 0), 0),
  test_cases: column.iterations.reduce((sum, iteration) => sum + (iteration.test_cases?.length || 0), 0),
  bugs: column.iterations.reduce((sum, iteration) => sum + (iteration.bugs?.length || 0), 0),
  total: column.total,
  children: column.iterations.map((iteration) => ({
    id: `${column.key}-${iteration.id}`,
    type: 'iteration',
    name: iteration.name,
    status: iteration.status,
    requirements: iteration.requirements?.length || 0,
    tasks: iteration.tasks?.length || 0,
    test_cases: iteration.test_cases?.length || 0,
    bugs: iteration.bugs?.length || 0,
    total: boardTotal(iteration)
  }))
})))

const emptyDescription = computed(() => {
  if (viewMode.value === 'mine' && !currentUserId.value) {
    return '无法识别当前登录用户，请重新登录，或切换到全部工作查看数据'
  }
  return '暂无符合筛选条件的工作项'
})

watch(boardColumns, () => {
  const visibleKeys = new Set(boardColumns.value.flatMap((column) => column.iterations.map((iteration) => iteration.context_key)))
  const hasVisibleExpanded = [...expandedIterationIds.value].some((key) => visibleKeys.has(key))
  if (!hasVisibleExpanded) {
    const first = boardColumns.value[0]?.iterations?.[0]
    expandedIterationIds.value = first ? new Set([first.context_key]) : new Set()
  }
})

const bugActionTitle = computed(() => ({
  start_fixing: '确认 Bug',
  resolve: '解决 Bug',
  activate: '激活 Bug',
  suspend: '挂起 Bug',
  close: '关闭 Bug',
  verify_passed: '验证通过',
  verify_failed: '验证失败'
}[bugActionType.value] || 'Bug 操作'))

function filterItems(items) {
  const keyword = keywordFilter.value.trim().toLowerCase()
  const effectiveOwnerId = viewMode.value === 'mine' ? currentUserId.value : ownerFilter.value
  return items
    .filter((item) => viewMode.value !== 'mine' || Boolean(effectiveOwnerId))
    .filter((item) => !effectiveOwnerId || item.owner_id === effectiveOwnerId)
    .filter((item) => !typeFilter.value || item.object_type === typeFilter.value)
    .filter((item) => !keyword || `${item.title || ''} ${item.project_name || ''}`.toLowerCase().includes(keyword))
    .map((item) => ({ ...item, drag_key: `${item.object_type}-${item.id}` }))
}
function iterationForProjectColumn(iteration, project, columnKey) {
  return {
    ...iteration,
    context_key: `${columnKey}-iteration-${iteration.id}`,
    requirements: filterItemsForProject(iteration.requirements, project.id),
    tasks: filterItemsForProject(iteration.tasks, project.id),
    test_cases: filterItemsForProject(iteration.test_cases, project.id),
    bugs: filterItemsForProject(iteration.bugs, project.id)
  }
}
function filterItemsForProject(items = [], projectId) {
  if (projectId === 'unbound') return items.filter((item) => !item.project_id)
  return items.filter((item) => item.project_id === projectId)
}
function decorateListItem(item, iteration) {
  return {
    ...item,
    iteration_name: iteration.name,
    iteration_status: iteration.status
  }
}
function sortIterationsForBoard(items) {
  return [...items].sort(compareIterationsForWorkbench)
}
function compareIterationsForWorkbench(a, b) {
  const aHasStart = Boolean(a.start_date)
  const bHasStart = Boolean(b.start_date)
  if (aHasStart !== bHasStart) return aHasStart ? -1 : 1
  if (aHasStart && a.start_date !== b.start_date) return a.start_date.localeCompare(b.start_date)
  const aCreated = a.create_time || ''
  const bCreated = b.create_time || ''
  if (aCreated !== bCreated) return aCreated.localeCompare(bCreated)
  return a.id - b.id
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
function laneKey(iterationId, groupKey) { return `${iterationId}-${groupKey}` }
function laneLimit(iterationId, groupKey) { return laneLimits[laneKey(iterationId, groupKey)] || INITIAL_LANE_LIMIT }
function visibleLaneItems(iterationId, groupKey, items) { return items.slice(0, laneLimit(iterationId, groupKey)) }
function hiddenLaneCount(iterationId, groupKey, items) { return Math.max(0, items.length - laneLimit(iterationId, groupKey)) }
function hasHiddenLaneItems(iterationId, groupKey, items) { return hiddenLaneCount(iterationId, groupKey, items) > 0 }
function showMoreLaneItems(iterationId, groupKey) { laneLimits[laneKey(iterationId, groupKey)] = laneLimit(iterationId, groupKey) + LANE_LIMIT_STEP }
function isIterationExpanded(iterationId) { return expandedIterationIds.value.has(iterationId) }
function toggleIteration(iterationId) {
  const next = new Set(expandedIterationIds.value)
  if (next.has(iterationId)) next.delete(iterationId)
  else next.add(iterationId)
  expandedIterationIds.value = next
}
function ensureExpandedIteration() {
  if (expandedIterationIds.value.size) return
  const first = boardColumns.value[0]?.iterations?.[0]
  if (first) expandedIterationIds.value = new Set([first.context_key])
}
function ownerName(id) { return owners.value.find((item) => item.id === id)?.full_name || '未分配' }
function typeLabel(value) { return itemTypes.find((item) => item.value === value)?.label || value }
function typeShortLabel(value) { return { requirement: '需', task: '任', test_case: '测', bug: 'Bug', code_review: 'CR' }[value] || typeLabel(value) }
function typeTag(value) { return { requirement: 'primary', task: 'success', test_case: 'warning', bug: 'danger', code_review: 'info' }[value] || 'info' }
function iterationStatusLabel(value) { return statusOptions.iteration[value] || value || '-' }
function itemStatusLabel(item) {
  const status = item.object_type === 'test_case' ? executionResultLabel(item.last_execute_result) : (statusOptions[item.object_type]?.[item.status] || item.status || '-')
  return item.marker ? `${status} · ${item.marker}` : status
}
function executionResultLabel(value) { return executionResultOptions.find((item) => item.value === value)?.label || value || '未执行' }
function canCreateBugFromCase(item) { return ['failed', 'blocked'].includes(item.last_execute_result) }
function openWorkItemDrawer(item, iteration = null) {
  if (item.object_type === 'code_review') {
    router.push({ name: 'devops' })
    return
  }
  selectedWorkItem.value = iteration ? decorateListItem(item, iteration) : item
  workItemDrawerVisible.value = true
}
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
    const currentUserId = Number(localStorage.getItem('current_user_id') || 0) || undefined
    const { data } = await fetchWorkbench(currentUserId ? { user_id: currentUserId } : {})
    iterations.value = data.iterations || []
    owners.value = data.owners || []
    reviewTasks.value = data.review_tasks || []
    ensureExpandedIteration()
    refreshSelectedWorkItem()
  } catch (error) {
    ElMessage.error('工作台加载失败，请确认后端服务已启动')
  } finally {
    loading.value = false
  }
}

function refreshSelectedWorkItem() {
  if (!selectedWorkItem.value) return
  const latest = flatWorkbenchItems.value.find((item) => item.object_type === selectedWorkItem.value.object_type && item.id === selectedWorkItem.value.id)
  if (latest) selectedWorkItem.value = latest
  else workItemDrawerVisible.value = false
}

watch(viewMode, (value) => {
  if (value === 'mine') ownerFilter.value = null
})
function onDragStart() {
  dragSnapshot.value = JSON.parse(JSON.stringify(iterations.value))
}
async function onDragAdd(event, targetIterationId) {
  const objectId = Number(event?.item?.dataset?.id)
  const objectType = event?.item?.dataset?.type
  if (!objectId || !objectType) return loadWorkbench()
  const draggedItem = findWorkbenchItem(objectType, objectId)
  const targetIteration = iterations.value.find((item) => item.id === targetIterationId)
  if (!draggedItem || !targetIteration) return loadWorkbench()
  if (draggedItem.iteration_id === targetIterationId) return loadWorkbench()
  try {
    await ElMessageBox.confirm(
      `确认将「${draggedItem.title}」从「${draggedItem.iteration_name || '-'}」转移到「${targetIteration.name}」吗？`,
      '确认转移迭代',
      { type: 'warning', confirmButtonText: '确认转移', cancelButtonText: '取消' }
    )
    await moveWorkbenchItem({ object_type: objectType, object_id: objectId, target_iteration_id: targetIterationId })
    await loadWorkbench()
    ElMessage.success('已移动到目标迭代')
  } catch (error) {
    if (dragSnapshot.value) iterations.value = dragSnapshot.value
    if (error === 'cancel' || error === 'close') return
    ElMessageBox.alert(error?.response?.data?.detail || '移动失败', '提示', { type: 'warning' })
  }
}
function findWorkbenchItem(objectType, objectId) {
  return flatWorkbenchItems.value.find((item) => item.object_type === objectType && item.id === objectId)
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
