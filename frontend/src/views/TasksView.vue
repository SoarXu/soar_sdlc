<template>
  <section>
    <div class="page-head">
      <div>
        <h1>任务</h1>
        <p>维护研发执行任务，关联项目、需求和当前处理人均以名称展示。</p>
      </div>
      <el-button v-if="canCreateAnyTask" type="primary" @click="openCreate">新增任务</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="pagedTasks" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="任务标题" min-width="220" />
        <el-table-column label="项目" width="180"><template #default="{ row }">{{ labelById(projects, row.project_id) }}</template></el-table-column>
        <el-table-column label="来源项目" width="180"><template #default="{ row }">{{ labelById(projects, row.source_project_id) }}</template></el-table-column>
        <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(requirements, row.requirement_id, 'title') }}</template></el-table-column>
        <el-table-column label="任务分支" width="120"><template #default="{ row }">{{ taskBranchLabel(row.task_type) }}</template></el-table-column>
        <el-table-column label="当前处理人" width="150"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column prop="due_date" label="截止日期" width="130" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tooltip v-if="closeReasonByTask[row.id]" :content="closeReasonByTask[row.id]" placement="top" raw-content>
              <span class="status-with-reason">{{ taskStatusLabel(row.status) }}</span>
            </el-tooltip>
            <span v-else>{{ taskStatusLabel(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="330" fixed="right">
          <template #default="{ row }">
            <WatchToggleButton object-type="task" :object-id="row.id" />
            <WorkflowActionButtons object-type="task" :object-id="row.id" mode="list" :transitions="workflowTransitionsFor(row)" :auto-load="false" :users="users" @command="handleWorkflowCommand(row, $event)" @executed="loadData" /><el-popconfirm v-if="canDeleteTaskRow(row)" title="确认删除该任务？" @confirm="removeTask(row.id)">
              <template #reference><el-button link type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-pagination">
        <el-pagination
          v-model:current-page="taskPage"
          v-model:page-size="taskPageSize"
          :page-sizes="taskPageSizes"
          :total="taskTotal"
          layout="total, sizes, prev, pager, next, jumper"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑任务' : '新增任务'" width="620px">
      <el-form label-position="top">
        <el-form-item label="任务标题" required><el-input v-model="form.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目" required>
            <el-select v-model="form.project_id" filterable placeholder="请选择项目" @change="onProjectChange">
              <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="来源项目">
            <el-select v-model="form.source_project_id" clearable filterable placeholder="请选择来源项目" @change="onSourceProjectChange">
              <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="需求">
            <el-select v-model="form.requirement_id" clearable filterable placeholder="请选择需求" @change="onRequirementChange">
              <el-option v-for="requirement in availableRequirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="任务分支" required>
            <el-select v-model="form.task_type" :disabled="Boolean(form.requirement_id)">
              <el-option v-for="option in TASK_BRANCH_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="!editingId" label="当前处理人">
            <el-select v-model="form.owner_id" clearable filterable placeholder="请选择当前处理人" @change="onOwnerChange">
              <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="截止日期"><el-date-picker v-model="form.due_date" value-format="YYYY-MM-DD" type="date" /></el-form-item>
        </div>
        <el-form-item label="优先级"><el-select v-model="form.priority"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitTask">保存</el-button></template>
    </el-dialog>

    
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchProjectMembers, fetchProjects } from '../api/projects'
import { fetchRequirements } from '../api/requirements'
import { createTask, deleteTask, fetchTasks, fetchTaskStatusOperations, updateTask } from '../api/tasks'
import { fetchUsers } from '../api/users'
import { fetchWorkflowTransitionsBatch } from '../api/workflowRuntime'
import WorkflowActionButtons from '../components/WorkflowActionButtons.vue'
import WatchToggleButton from '../components/WatchToggleButton.vue'
import { showActionError } from '../utils/actionFeedback'
import { canCreateWorkItem, canDeleteWorkItem, currentUserFromStorage } from '../utils/permissions'
import { labelById, userLabel } from '../utils/referenceLabels'
import { loadCloseReasonMap } from '../utils/closeReasonTooltip'
import { usePagination } from '../utils/usePagination'
import { deriveTaskBranch, TASK_BRANCH_OPTIONS, taskBranchLabel } from '../utils/taskBranchRules'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const tasks = ref([])
const closeReasonByTask = ref({})
const workflowTransitions = ref({})
const projects = ref([])
const projectMembersById = ref({})
const requirements = ref([])
const users = ref([])
const currentUser = computed(() => currentUserFromStorage(users.value))
const canCreateAnyTask = computed(() => projects.value.some((project) => canCreateWorkItem(project, currentUser.value, membersForProject(project.id))))
const {
  page: taskPage,
  pageSize: taskPageSize,
  pageSizes: taskPageSizes,
  total: taskTotal,
  pagedItems: pagedTasks
} = usePagination(tasks)
const form = reactive({ project_id: null, source_project_id: null, requirement_id: null, title: '', task_type: 'standalone_operation', priority: 'medium', owner_id: null, due_date: null, description: '' })
const ownerManuallySet = ref(false)
const availableRequirements = computed(() => {
  if (!form.project_id) return requirements.value
  return requirements.value.filter((item) => item.project_id === form.project_id)
})
const taskStatusOptions = [
  { label: '待分派', value: 'pending_assignment' },
  { label: '处理中', value: 'in_processing' },
  { label: '待确认', value: 'pending_confirmation' },
  { label: '已完成', value: 'completed' },
  { label: '已取消', value: 'canceled' }
]

function optionLabel(options, value) { return options.find((option) => option.value === value)?.label || value || '-' }
function taskStatusLabel(value) { return optionLabel(taskStatusOptions, value) }
function isTaskProjectClosed(row) { return projects.value.find((item) => item.id === row.project_id)?.status === 'closed' }
function workflowTransitionsFor(row) { return workflowTransitions.value[`task:${row.id}`] || [] }
function projectForTask(row) { return projects.value.find((item) => item.id === row.project_id) || null }
function membersForProject(projectId) { return projectMembersById.value[projectId] || [] }
function canDeleteTaskRow(row) {
  const project = projectForTask(row)
  return !isTaskProjectClosed(row) && canDeleteWorkItem(project, currentUser.value, membersForProject(project?.id))
}
function resetForm() { Object.assign(form, { project_id: null, source_project_id: null, requirement_id: null, title: '', task_type: 'standalone_operation', priority: 'medium', owner_id: null, due_date: null, description: '' }); ownerManuallySet.value = false }
function openCreate() { editingId.value = null; resetForm(); dialogVisible.value = true }
function openEdit(row) {
  editingId.value = row.id
  ownerManuallySet.value = true
  Object.assign(form, {
    project_id: row.project_id || null,
    source_project_id: row.source_project_id || null,
    requirement_id: row.requirement_id || null,
    title: row.title || '',
    task_type: deriveTaskBranch({ requirementId: row.requirement_id, currentType: row.task_type }),
    priority: row.priority || 'medium',
    owner_id: row.owner_id || null,
    due_date: row.due_date || null,
    description: row.description || ''
  })
  dialogVisible.value = true
}
function handleWorkflowCommand(row, { commandType }) {
  if (commandType === 'edit') openEdit(row)
  if (commandType === 'view_history') router.push(`/tasks/${row.id}#history`)
}
function onSourceProjectChange() {}
function onProjectChange(projectId) {
  const requirement = requirements.value.find((item) => item.id === form.requirement_id)
  if (requirement && requirement.project_id !== projectId) form.requirement_id = null
  if (!ownerManuallySet.value) form.owner_id = null
}
function onRequirementChange(requirementId) {
  form.task_type = deriveTaskBranch({ requirementId, currentType: requirementId ? null : form.task_type })
  if (ownerManuallySet.value) return
  form.owner_id = null
}
function onOwnerChange() { ownerManuallySet.value = true }

async function loadData() {
  loading.value = true
  try {
    const [taskRes, projectRes, reqRes, userRes] = await Promise.all([fetchTasks(), fetchProjects(), fetchRequirements(), fetchUsers()])
    tasks.value = taskRes.data; projects.value = projectRes.data; requirements.value = reqRes.data; users.value = userRes.data
    await loadProjectMembers()
    closeReasonByTask.value = await loadCloseReasonMap(tasks.value, fetchTaskStatusOperations)
    await loadWorkflowTransitions()
  } catch { ElMessage.error('任务列表加载失败') } finally { loading.value = false }
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

async function loadWorkflowTransitions() {
  if (!tasks.value.length) {
    workflowTransitions.value = {}
    return
  }
  const { data } = await fetchWorkflowTransitionsBatch(tasks.value.map((item) => ({ object_type: 'task', id: item.id })))
  workflowTransitions.value = Object.fromEntries((data.items || []).map((item) => [`${item.object_type}:${item.id}`, item.transitions || []]))
}
async function submitTask() {
  if (!form.project_id || !form.title.trim()) return ElMessage.warning('请选择项目并填写任务标题')
  saving.value = true
  try {
    const payload = {
      ...form,
      requirement_id: form.requirement_id || null,
      task_type: deriveTaskBranch({ requirementId: form.requirement_id, currentType: form.task_type }),
      owner_id: form.owner_id || null
    }
    if (editingId.value) await updateTask(editingId.value, payload); else await createTask(payload)
    dialogVisible.value = false; await loadData()
  } catch (error) {
    showActionError(error, editingId.value ? '任务保存失败' : '任务创建失败')
  } finally { saving.value = false }
}
async function removeTask(id) {
  try {
    await deleteTask(id)
    await loadData()
  } catch (error) {
    showActionError(error, '任务删除失败')
  }
}
onMounted(loadData)
</script>
