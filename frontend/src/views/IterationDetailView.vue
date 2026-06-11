<template>
  <section class="project-detail-page">
    <div class="project-detail-head">
      <div>
        <el-button link type="primary" @click="$router.push('/iterations')">返回迭代列表</el-button>
        <h1>{{ iteration.name || '迭代详情' }}</h1>
        <p>{{ projectNames }} · {{ userLabel(users, iteration.owner_id) }} · {{ iteration.start_date || '-' }} 至 {{ iteration.end_date || '-' }}</p>
      </div>
      <el-tag size="large">{{ iterationStatusLabel(iteration.status) }}</el-tag>
    </div>

    <div class="project-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="project-tab-button"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="setActiveTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </div>

    <el-card v-loading="loading" shadow="never" class="project-detail-card">
      <template v-if="activeTab === 'overview'">
        <div class="metrics project-detail-metrics">
          <el-card shadow="never"><span>需求数</span><strong>{{ metrics.requirement_total || 0 }}</strong></el-card>
          <el-card shadow="never"><span>任务数</span><strong>{{ tasks.length }}</strong></el-card>
          <el-card shadow="never"><span>用例数</span><strong>{{ testCases.length }}</strong></el-card>
          <el-card shadow="never"><span>Bug 数</span><strong>{{ bugs.length }}</strong></el-card>
          <el-card shadow="never"><span>迭代进度</span><strong>{{ percent(metrics.progress_rate) }}</strong></el-card>
          <el-card shadow="never"><span>测试覆盖率</span><strong>{{ percent(metrics.test_coverage_rate) }}</strong></el-card>
        </div>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="迭代名称">{{ iteration.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="负责人">{{ userLabel(users, iteration.owner_id) }}</el-descriptions-item>
          <el-descriptions-item label="开始日期">{{ iteration.start_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="结束日期">{{ iteration.end_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="目标" :span="2">{{ iteration.goal || '-' }}</el-descriptions-item>
        </el-descriptions>
      </template>

      <template v-else-if="activeTab === 'requirements'">
        <div class="project-tab-toolbar"><el-button type="primary" @click="openRequirementLink">关联需求</el-button></div>
        <div v-if="!requirements.length" class="project-tab-placeholder">暂无关联需求</div>
        <div v-else class="iteration-tree-list">
          <div v-for="project in flatProjects" :key="project.id" class="iteration-project-block">
            <h3 v-if="requirementsByProject(project.id).length">{{ project.name }}</h3>
            <el-table v-if="requirementsByProject(project.id).length" :data="requirementsByProject(project.id)" stripe width="100%">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column label="需求标题" min-width="180" show-overflow-tooltip>
                <template #default="{ row }"><router-link class="table-link" :to="requirementDetailLink(row)">{{ row.title }}</router-link></template>
              </el-table-column>
              <el-table-column label="迭代" width="140"><template #default>{{ iteration.name || '-' }}</template></el-table-column>
              <el-table-column label="负责人" width="130"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
              <el-table-column label="优先级" width="100"><template #default="{ row }"><RequirementPriorityBadge :value="row.priority" /></template></el-table-column>
              <el-table-column label="评审状态" width="110"><template #default="{ row }">{{ reviewStatusLabel(row.review_status) }}</template></el-table-column>
              <el-table-column label="状态" width="90">
                <template #default="{ row }">
                  <el-tooltip v-if="closeReasonByRequirement[row.id]" :content="closeReasonByRequirement[row.id]" placement="top" raw-content>
                    <span class="status-with-reason">{{ requirementStatusLabel(row.status) }}</span>
                  </el-tooltip>
                  <span v-else>{{ requirementStatusLabel(row.status) }}</span>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="420" fixed="right">
                <template #default="{ row }">
                  <div class="table-actions">
                    <el-button link type="primary" @click="goProjectTab(row.project_id, 'requirements')">编辑</el-button>
                    <el-button v-if="canActivateRequirement(row)" link type="warning" @click="activateRequirementRow(row.id)">激活</el-button>
                    <el-button v-if="row.status === 'active'" link type="danger" @click="openRequirementClose(row)">关闭</el-button>
                    <el-button link type="success" @click="goProjectTab(row.project_id, 'requirements')">生成任务</el-button>
                    <el-button link type="success" @click="goProjectTab(row.project_id, 'tests')">建用例</el-button>
                    <el-popconfirm title="确认删除该需求？" @confirm="deleteRequirementRow(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
                    <el-button link type="danger" @click="removeRequirement(row.id)">移除</el-button>
                  </div>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </template>

      <template v-else-if="activeTab === 'tasks'">
        <div class="project-tab-toolbar"><el-button type="primary" @click="openTaskLink">关联任务</el-button></div>
        <div v-for="project in flatProjects" :key="project.id" class="iteration-project-block">
          <h3 v-if="tasksByProject(project.id).length">{{ project.name }}</h3>
          <el-table v-if="tasksByProject(project.id).length" :data="tasksByProject(project.id)" stripe width="100%">
            <el-table-column prop="id" label="ID" width="80" />
            <el-table-column label="任务标题" min-width="180" show-overflow-tooltip><template #default="{ row }"><router-link class="table-link" :to="taskDetailLink(row)">{{ row.title }}</router-link></template></el-table-column>
            <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(requirements, row.requirement_id, 'title') }}</template></el-table-column>
            <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
            <el-table-column prop="actual_hours" label="实际工时" width="110" />
            <el-table-column prop="due_date" label="截止日期" width="130" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tooltip v-if="closeReasonByTask[row.id]" :content="closeReasonByTask[row.id]" placement="top" raw-content>
                  <span class="status-with-reason">{{ taskStatusLabel(row.status) }}</span>
                </el-tooltip>
                <span v-else>{{ taskStatusLabel(row.status) }}</span>
              </template>
            </el-table-column>
            <el-table-column label="操作" width="300" fixed="right">
              <template #default="{ row }">
                <div class="table-actions">
                  <el-button link type="primary" @click="goProjectTab(row.project_id, 'tasks')">编辑</el-button>
                  <el-button v-if="canActivateTask(row)" link type="warning" @click="activateTaskRow(row.id)">激活</el-button>
                  <el-button v-if="row.status !== 'closed'" link type="danger" @click="openTaskClose(row)">关闭</el-button>
                  <el-popconfirm title="确认删除该任务？" @confirm="deleteTaskRow(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
                  <el-button v-if="row.iteration_id === iterationId" link type="danger" @click="removeTask(row.id)">移除</el-button>
                  <span v-else class="muted-text">需求带入</span>
                </div>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </template>

      <template v-else-if="activeTab === 'cases'">
        <div v-if="!testCases.length" class="project-tab-placeholder">暂无关联用例</div>
        <div v-else class="iteration-tree-list">
          <div v-for="project in flatProjects" :key="project.id" class="iteration-project-block">
            <h3 v-if="testCasesByProject(project.id).length">{{ project.name }}</h3>
            <el-table v-if="testCasesByProject(project.id).length" :data="testCasesByProject(project.id)" stripe width="100%">
              <el-table-column prop="id" label="ID" width="80" />
              <el-table-column prop="title" label="用例标题" min-width="180" show-overflow-tooltip />
              <el-table-column label="需求" min-width="180"><template #default="{ row }">{{ labelById(requirements, row.requirement_id, 'title') }}</template></el-table-column>
              <el-table-column label="类型" width="120"><template #default="{ row }">{{ caseTypeLabel(row.case_type) }}</template></el-table-column>
              <el-table-column label="适用范围" width="150"><template #default="{ row }">{{ testScopeLabel(row.test_scope) }}</template></el-table-column>
              <el-table-column label="最近执行时间" width="170"><template #default="{ row }">{{ formatDateTime(row.last_execute_time) }}</template></el-table-column>
              <el-table-column label="最近结果" width="110"><template #default="{ row }">{{ executionResultLabel(row.last_execute_result) }}</template></el-table-column>
              <el-table-column label="操作" width="150" fixed="right"><template #default="{ row }"><el-button link type="success" @click="openCaseExecution(row)">执行</el-button><el-button link type="warning" :disabled="!canCreateBugFromCase(row)" @click="openCaseBug(row)">提 Bug</el-button></template></el-table-column>
            </el-table>
          </div>
        </div>
      </template>

      <template v-else-if="activeTab === 'bugs'">
        <el-table :data="bugs" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="title" label="Bug 标题" min-width="180" show-overflow-tooltip />
          <el-table-column label="项目" width="180"><template #default="{ row }">{{ labelById(flatProjects, row.project_id) }}</template></el-table-column>
          <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(requirements, row.requirement_id, 'title') }}</template></el-table-column>
          <el-table-column label="Bug 类型" width="120"><template #default="{ row }">{{ row.bug_type || '-' }}</template></el-table-column>
          <el-table-column label="严重程度" width="110"><template #default="{ row }"><RequirementPriorityBadge :value="row.severity" /></template></el-table-column>
          <el-table-column label="优先级" width="110"><template #default="{ row }"><RequirementPriorityBadge :value="row.priority" /></template></el-table-column>
          <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          <el-table-column label="状态" width="110"><template #default="{ row }">{{ bugStatusLabel(row.status) }}</template></el-table-column>
        </el-table>
      </template>
    </el-card>

    <el-dialog v-model="requirementDialogVisible" title="关联需求" width="760px">
      <el-table :data="availableRequirements" @selection-change="selectedRequirementIds = $event.map(item => item.id)" max-height="420">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="title" label="需求标题" min-width="240" />
        <el-table-column label="项目" width="180"><template #default="{ row }">{{ labelById(flatProjects, row.project_id) }}</template></el-table-column>
        <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="{ row }">{{ requirementStatusLabel(row.status) }}</template></el-table-column>
      </el-table>
      <template #footer><el-button @click="requirementDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRequirements">关联</el-button></template>
    </el-dialog>

    <el-dialog v-model="taskDialogVisible" title="关联任务" width="760px">
      <el-table :data="availableTasks" @selection-change="selectedTaskIds = $event.map(item => item.id)" max-height="420">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="title" label="任务标题" min-width="240" />
        <el-table-column label="项目" width="180"><template #default="{ row }">{{ labelById(flatProjects, row.project_id) }}</template></el-table-column>
        <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="{ row }">{{ taskStatusLabel(row.status) }}</template></el-table-column>
      </el-table>
      <template #footer><el-button @click="taskDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitTasks">关联</el-button></template>
    </el-dialog>

    <el-dialog v-model="closeRequirementVisible" title="关闭需求" width="480px">
      <el-form label-position="top">
        <el-form-item label="关闭原因" required>
          <el-select v-model="closeRequirementForm.reason" placeholder="请选择关闭原因">
            <el-option v-for="option in requirementCloseReasons" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="closeRequirementForm.remark" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="closeRequirementVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRequirementClose">确认关闭</el-button></template>
    </el-dialog>

    <el-dialog v-model="closeTaskVisible" title="关闭任务" width="480px">
      <el-form label-position="top">
        <el-form-item label="关闭原因" required>
          <el-select v-model="closeTaskForm.reason" placeholder="请选择关闭原因">
            <el-option v-for="option in taskCloseReasons" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="closeTaskForm.remark" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="closeTaskVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitTaskClose">确认关闭</el-button></template>
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
          <el-form-item label="严重程度"><el-select v-model="caseBugForm.severity"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item>
          <el-form-item label="优先级"><el-select v-model="caseBugForm.priority"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item>
        </div>
        <el-form-item label="重现步骤"><el-input v-model="caseBugForm.reproduce_steps" type="textarea" :rows="8" /></el-form-item>
        <el-form-item label="实际结果"><el-input v-model="caseBugForm.actual_result" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="caseBugVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitCaseBug">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  fetchAvailableIterationRequirements,
  fetchAvailableIterationTasks,
  fetchIterationDetail,
  linkIterationRequirements,
  linkIterationTasks,
  unlinkIterationRequirement,
  unlinkIterationTask
} from '../api/iterations'
import { createBugFromTestCase, executeTestCase, fetchTestCaseExecutions } from '../api/testCases'
import { activateRequirement, closeRequirement, deleteRequirement, fetchRequirementStatusOperations } from '../api/requirements'
import { activateTask, closeTask, deleteTask, fetchTaskStatusOperations } from '../api/tasks'
import { fetchUsers } from '../api/users'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import { labelById, userLabel } from '../utils/referenceLabels'

const route = useRoute()
const router = useRouter()
const iterationId = computed(() => Number(route.params.id))
const loading = ref(false)
const saving = ref(false)
const activeTab = ref(normalizeIterationTab(route.query.tab))
const iteration = ref({})
const projects = ref([])
const requirements = ref([])
const tasks = ref([])
const testCases = ref([])
const bugs = ref([])
const metrics = ref({})
const users = ref([])
const availableRequirements = ref([])
const availableTasks = ref([])
const selectedRequirementIds = ref([])
const selectedTaskIds = ref([])
const requirementDialogVisible = ref(false)
const taskDialogVisible = ref(false)
const closeRequirementVisible = ref(false)
const closeTaskVisible = ref(false)
const closingRequirementId = ref(null)
const closingTaskId = ref(null)
const caseExecutionVisible = ref(false)
const caseBugVisible = ref(false)
const selectedCase = ref(null)
const bugSourceCase = ref(null)
const caseExecutionHistory = ref([])
const caseExecutionForm = ref({ execute_time: '', steps_result_json: [] })
const closeReasonByRequirement = ref({})
const closeReasonByTask = ref({})
const tabs = [
  { key: 'overview', label: '概览' },
  { key: 'requirements', label: '需求' },
  { key: 'tasks', label: '任务' },
  { key: 'cases', label: '用例' },
  { key: 'bugs', label: 'Bug' }
]
const iterationStatusOptions = [
  { label: '规划中', value: 'planning' },
  { label: '进行中', value: 'active' },
  { label: '已完成', value: 'finished' },
  { label: '已关闭', value: 'closed' }
]
const requirementStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '激活', value: 'active' },
  { label: '完成', value: 'done' },
  { label: '关闭', value: 'closed' }
]
const reviewStatusOptions = [
  { label: '无需评审', value: 'not_required' },
  { label: '待评审', value: 'pending' },
  { label: '已通过', value: 'approved' },
  { label: '已拒绝', value: 'rejected' }
]
const requirementCloseReasons = ['已完成', '不做', '重复', '延期', '需求变更']
const taskCloseReasons = ['已完成', '不做', '重复', '需求关闭', '其他']
const taskStatusOptions = [
  { label: '待办', value: 'todo' },
  { label: '进行中', value: 'doing' },
  { label: '完成', value: 'done' },
  { label: '关闭', value: 'closed' }
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
const executionResultOptions = [
  { label: '忽略', value: 'ignored' },
  { label: '通过', value: 'passed' },
  { label: '失败', value: 'failed' },
  { label: '阻塞', value: 'blocked' }
]
const bugStatusOptions = [
  { label: '待修复', value: 'open' },
  { label: '修复中', value: 'fixing' },
  { label: '待验证', value: 'verifying' },
  { label: '已关闭', value: 'closed' },
  { label: '重新打开', value: 'reopened' }
]
const bugTypeOptions = ['代码错误', '配置相关', '安装部署', '安全相关', '性能问题', '标准规范', '测试脚本', '设计缺陷', '其他']
const priorityLevelOptions = [
  { label: '① 最高', value: '1' },
  { label: '② 高', value: '2' },
  { label: '③ 中', value: '3' },
  { label: '④ 低', value: '4' },
  { label: '⑤ 最低', value: '5' }
]
const caseBugForm = ref({ title: '', bug_type: '代码错误', severity: '3', priority: '3', reproduce_steps: '', actual_result: '' })
const closeRequirementForm = reactive({ reason: '', remark: '' })
const closeTaskForm = reactive({ reason: '', remark: '' })
const flatProjects = computed(() => flattenProjects(projects.value))
const projectNames = computed(() => (iteration.value.project_ids || []).map(id => labelById(flatProjects.value, id)).join('、') || '-')
const failedExecutionCount = computed(() => caseExecutionHistory.value.filter((item) => item.result === 'failed').length)

function optionLabel(options, value) { return options.find((option) => option.value === value)?.label || value || '-' }
function iterationStatusLabel(value) { return optionLabel(iterationStatusOptions, value) }
function requirementStatusLabel(value) { return optionLabel(requirementStatusOptions, value) }
function reviewStatusLabel(value) { return optionLabel(reviewStatusOptions, value) }
function taskStatusLabel(value) { return optionLabel(taskStatusOptions, value) }
function bugStatusLabel(value) { return optionLabel(bugStatusOptions, value) }
function caseTypeLabel(value) { return optionLabel(caseTypeOptions, value) }
function testScopeLabel(value) { return optionLabel(testScopeOptions, value) }
function executionResultLabel(value) { return optionLabel(executionResultOptions, value) }
function canCreateBugFromCase(row) { return ['failed', 'blocked'].includes(row.last_execute_result) }
function canActivateRequirement(row) { return ['draft', 'closed'].includes(row.status) }
function canActivateTask(row) { return ['todo', 'closed'].includes(row.status) }
function requirementsByProject(projectId) { return requirements.value.filter((item) => item.project_id === projectId) }
function tasksByProject(projectId) { return tasks.value.filter((item) => item.project_id === projectId) }
function testCasesByProject(projectId) { return testCases.value.filter((item) => item.project_id === projectId) }
function requirementDetailLink(row) { return { name: 'requirement-detail', params: { id: row.id }, query: { from: 'iteration', iterationId: iterationId.value, tab: 'requirements' } } }
function taskDetailLink(row) { return { name: 'task-detail', params: { id: row.id }, query: { from: 'iteration', iterationId: iterationId.value, tab: 'tasks' } } }
function percent(value) { return `${Math.round((value || 0) * 100)}%` }
function flattenProjects(items) { return items.flatMap((item) => [item, ...flattenProjects(item.children || [])]) }
function formatDateTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-' }
function executionHistoryTitle(item) { return `#${item.id} ${formatDateTime(item.execute_time)}，结果为 ${executionResultLabel(item.result)}` }
function defaultExecutionTime() {
  const date = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
function normalizeCaseSteps(value) { return Array.isArray(value) && value.length ? value.map((item) => ({ step: item.step || '', expected: item.expected || '' })) : [{ step: '', expected: '' }] }
function normalizeIterationTab(value) { return ['overview', 'requirements', 'tasks', 'cases', 'bugs'].includes(value) ? value : 'overview' }
function setActiveTab(key) {
  activeTab.value = key
  router.replace({ name: 'iteration-detail', params: { id: iterationId.value }, query: { ...route.query, tab: key } })
}
function apiErrorMessage(error, fallback) { return error?.response?.data?.detail || fallback }
function showActionError(error, fallback) { ElMessageBox.alert(apiErrorMessage(error, fallback), '提示', { type: 'warning' }) }
function goProjectTab(projectId, tab) { router.push({ name: 'project-detail', params: { id: projectId }, query: { tab } }) }

async function loadData() {
  loading.value = true
  try {
    const [detailRes, userRes] = await Promise.all([fetchIterationDetail(iterationId.value), fetchUsers()])
    iteration.value = detailRes.data.iteration
    projects.value = detailRes.data.projects
    requirements.value = detailRes.data.requirements
    tasks.value = detailRes.data.tasks
    testCases.value = detailRes.data.test_cases
    bugs.value = detailRes.data.bugs || []
    metrics.value = detailRes.data.metrics
    users.value = userRes.data
    closeReasonByRequirement.value = await loadCloseReasonMap(requirements.value, fetchRequirementStatusOperations)
    closeReasonByTask.value = await loadCloseReasonMap(tasks.value, fetchTaskStatusOperations)
  } catch {
    ElMessage.error('迭代详情加载失败')
  } finally {
    loading.value = false
  }
}

async function openRequirementLink() {
  selectedRequirementIds.value = []
  availableRequirements.value = (await fetchAvailableIterationRequirements(iterationId.value)).data
  requirementDialogVisible.value = true
}
async function submitRequirements() {
  if (!selectedRequirementIds.value.length) return ElMessage.warning('请选择需求')
  saving.value = true
  try {
    await linkIterationRequirements(iterationId.value, selectedRequirementIds.value)
    requirementDialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}
async function removeRequirement(requirementId) { await unlinkIterationRequirement(iterationId.value, requirementId); await loadData() }
async function activateRequirementRow(id) { try { await activateRequirement(id); await loadData(); ElMessage.success('需求已激活') } catch (error) { showActionError(error, '需求激活失败') } }
function openRequirementClose(row) { closingRequirementId.value = row.id; Object.assign(closeRequirementForm, { reason: '', remark: '' }); closeRequirementVisible.value = true }
async function submitRequirementClose() { if (!closeRequirementForm.reason) return ElMessage.warning('请选择关闭原因'); saving.value = true; try { await closeRequirement(closingRequirementId.value, { ...closeRequirementForm }); closeRequirementVisible.value = false; await loadData(); ElMessage.success('需求已关闭') } catch (error) { showActionError(error, '需求关闭失败') } finally { saving.value = false } }
async function deleteRequirementRow(id) { await deleteRequirement(id); await loadData() }

async function openTaskLink() {
  selectedTaskIds.value = []
  availableTasks.value = (await fetchAvailableIterationTasks(iterationId.value)).data
  taskDialogVisible.value = true
}
async function submitTasks() {
  if (!selectedTaskIds.value.length) return ElMessage.warning('请选择任务')
  saving.value = true
  try {
    await linkIterationTasks(iterationId.value, selectedTaskIds.value)
    taskDialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}
async function removeTask(taskId) { await unlinkIterationTask(iterationId.value, taskId); await loadData() }
async function activateTaskRow(id) { try { await activateTask(id); await loadData(); ElMessage.success('任务已激活') } catch (error) { showActionError(error, '任务激活失败') } }
function openTaskClose(row) { closingTaskId.value = row.id; Object.assign(closeTaskForm, { reason: '', remark: '' }); closeTaskVisible.value = true }
async function submitTaskClose() { if (!closeTaskForm.reason) return ElMessage.warning('请选择关闭原因'); saving.value = true; try { await closeTask(closingTaskId.value, { ...closeTaskForm }); closeTaskVisible.value = false; await loadData(); ElMessage.success('任务已关闭') } catch (error) { showActionError(error, '任务关闭失败') } finally { saving.value = false } }
async function deleteTaskRow(id) { await deleteTask(id); await loadData() }
async function openCaseExecution(row) {
  selectedCase.value = row
  caseExecutionForm.value = {
    execute_time: defaultExecutionTime(),
    steps_result_json: normalizeCaseSteps(row.steps_json).map((item) => ({ ...item, result: 'passed', actual: '' }))
  }
  caseExecutionHistory.value = (await fetchTestCaseExecutions(row.id)).data
  caseExecutionVisible.value = true
}
async function openCaseBug(row) {
  if (!canCreateBugFromCase(row)) return
  bugSourceCase.value = row
  const history = (await fetchTestCaseExecutions(row.id)).data
  const latest = history[0]
  caseBugForm.value = {
    title: row.title,
    bug_type: '代码错误',
    severity: '3',
    priority: '3',
    reproduce_steps: buildReproduceText(latest, row),
    actual_result: buildActualText(latest)
  }
  caseBugVisible.value = true
}
async function submitCaseExecution() {
  saving.value = true
  try {
    const currentId = selectedCase.value.id
    await executeTestCase(currentId, { ...caseExecutionForm.value })
    await loadData()
    ElMessage.success('用例执行结果已保存')
    await openNextCaseAfterExecution(currentId, testCases.value)
  } finally {
    saving.value = false
  }
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

onMounted(loadData)
watch(() => route.query.tab, (value) => { activeTab.value = normalizeIterationTab(value) })

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
async function loadCloseReasonMap(items, fetcher) {
  const entries = await Promise.all(items.map(async (item) => {
    try {
      const operations = (await fetcher(item.id)).data
      const closeOperation = operations.find((operation) => operation.action === 'close' && operation.reason)
      return [item.id, closeOperation?.reason || '']
    } catch {
      return [item.id, '']
    }
  }))
  return Object.fromEntries(entries.filter(([, reason]) => reason))
}
</script>
