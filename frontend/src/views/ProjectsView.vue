<template>
  <section>
    <div class="page-head">
      <div>
        <h1>项目</h1>
        <p>维护项目归属、负责人、周期和状态，关联对象使用名称展示。</p>
      </div>
      <el-button v-if="canCreateProject" type="primary" @click="openCreate">新增项目</el-button>
    </div>

    <el-card shadow="never">
      <el-table
        v-loading="loading"
        class="project-tree-table"
        :data="pagedProjectTree"
        row-key="id"
        stripe
        default-expand-all
        :indent="PROJECT_TREE_INDENT"
        :tree-props="{ children: 'children' }"
      >
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column label="项目名称" min-width="180">
          <template #default="{ row }">
            <router-link class="table-link project-name-link" :style="projectNameIndentStyle(row)" :to="`/projects/${row.id}`">{{ row.name }}</router-link>
          </template>
        </el-table-column>
        <el-table-column label="所属项目集" width="180">
          <template #default="{ row }">{{ labelById(programs, row.program_id) }}</template>
        </el-table-column>
        <el-table-column label="负责人" width="150">
          <template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="130" />
        <el-table-column label="结束日期" width="130">
          <template #default="{ row }">{{ row.is_long_term ? '长期' : row.end_date }}</template>
        </el-table-column>
        <el-table-column prop="actual_start_date" label="实际开始" width="130" />
        <el-table-column prop="actual_end_date" label="实际结束" width="130" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">{{ row.status_name || '-' }}</template>
        </el-table-column>
        <el-table-column label="工作流方案" width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ workflowSchemeLabel(row.assignee_rule_config_id) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="330" fixed="right">
          <template #default="{ row }">
            <el-button v-if="canManageProjectRow(row)" link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canCreateProject" link type="success" @click="openCreate(row)">新增项目</el-button>
            <el-button v-if="canManageProjectRow(row) && (hasProjectAction(row, 'start') || hasProjectAction(row, 'resume'))" link type="success" @click="openStatusDialog(row, 'start')">启动</el-button>
            <el-button v-if="canManageProjectRow(row) && hasProjectAction(row, 'suspend')" link type="warning" @click="openStatusDialog(row, 'suspend')">挂起</el-button>
            <el-button v-if="canManageProjectRow(row) && hasProjectAction(row, 'close')" link type="danger" @click="openStatusDialog(row, 'close')">关闭</el-button>
            <el-button v-if="canManageProjectRow(row) && hasProjectAction(row, 'activate')" link type="success" @click="openStatusDialog(row, 'activate')">激活</el-button>
            <el-popconfirm v-if="canDeleteProjectRow" title="确认删除该项目？子项目将一并删除。" @confirm="removeProject(row.id)">
              <template #reference><el-button link type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-pagination">
        <el-pagination
          v-model:current-page="projectPage"
          v-model:page-size="projectPageSize"
          :page-sizes="projectPageSizes"
          :total="projectTotal"
          layout="total, sizes, prev, pager, next, jumper"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑项目' : '新增项目'" width="560px">
      <el-form label-position="top">
        <el-form-item label="项目名称" required><el-input v-model="form.name" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="上级项目">
            <el-select v-model="form.parent_id" clearable filterable placeholder="请选择上级项目">
              <el-option v-for="item in parentProjectOptions" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="所属项目集">
            <el-select v-model="form.program_id" clearable filterable placeholder="请选择项目集">
              <el-option v-for="program in programs" :key="program.id" :label="program.name" :value="program.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="负责人">
            <el-select v-model="form.owner_id" clearable filterable placeholder="请选择负责人">
              <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="工作流方案">
            <el-select v-model="form.assignee_rule_config_id" clearable filterable placeholder="请选择工作流方案">
              <el-option v-for="scheme in enabledWorkflowSchemes" :key="scheme.id" :label="scheme.name" :value="scheme.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="开始日期"><el-date-picker v-model="form.start_date" value-format="YYYY-MM-DD" type="date" /></el-form-item>
          <el-form-item label="结束日期">
            <div class="end-date-field">
              <el-checkbox v-model="form.is_long_term">长期</el-checkbox>
              <el-date-picker v-model="form.end_date" value-format="YYYY-MM-DD" type="date" :disabled="form.is_long_term" />
            </div>
          </el-form-item>
        </div>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitProject">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="statusDialogVisible" :title="statusDialogTitle" width="760px" class="status-operation-dialog">
      <el-form label-position="top">
        <el-form-item v-if="statusDateRequired" :label="statusDateLabel" required>
          <el-date-picker
            v-model="statusForm.effective_time"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            format="YYYY-MM-DD HH:mm:ss"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="statusForm.remark" type="textarea" :rows="5" placeholder="请输入本次操作备注" />
        </el-form-item>
      </el-form>
      <div class="status-history">
        <div class="status-history-title">历史记录</div>
        <el-empty v-if="!statusHistory.length" description="暂无历史记录" />
        <el-timeline v-else>
          <el-timeline-item v-for="item in statusHistory" :key="item.id" :timestamp="formatDateTime(item.effective_time)">
            <div>
              由 <strong>{{ item.actor_name || '系统' }}</strong> {{ statusActionLabel(item.action) }}。
              <el-tag size="small" effect="plain">{{ item.from_state_name || '-' }} → {{ item.to_state_name || '-' }}</el-tag>
            </div>
            <div v-if="item.remark" class="status-history-remark">{{ item.remark }}</div>
          </el-timeline-item>
        </el-timeline>
      </div>
      <template #footer>
        <el-button @click="statusDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitStatusOperation">{{ statusConfirmText }}</el-button>
      </template>
    </el-dialog>

  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchPrograms } from '../api/programs'
import { fetchAssigneeRuleConfigs } from '../api/assigneeRuleConfigs'
import {
  activateProject,
  closeProject,
  createProject,
  deleteProject,
  fetchProjectMembers,
  fetchProjectStatusOperations,
  fetchProjects,
  startProject,
  suspendProject,
  updateProject
} from '../api/projects'
import { fetchUsers } from '../api/users'
import { fetchWorkflowTransitionsBatch } from '../api/workflowRuntime'
import { showActionError } from '../utils/actionFeedback'
import { canDeleteProject, canManageProject, currentUserFromStorage, isSystemAdmin } from '../utils/permissions'
import { labelById, userLabel } from '../utils/referenceLabels'
import { usePagination } from '../utils/usePagination'
import { replaceWorkflowTransitionMap } from '../utils/workflowRuntimeActions'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const statusDialogVisible = ref(false)
const editingId = ref(null)
const statusTarget = ref(null)
const statusAction = ref('')
const statusHistory = ref([])
const projects = ref([])
const projectMembersById = ref({})
const programs = ref([])
const users = ref([])
const workflowSchemes = ref([])
const workflowTransitions = ref({})
const currentUser = computed(() => currentUserFromStorage(users.value))
const canCreateProject = computed(() => isSystemAdmin(currentUser.value))
const canDeleteProjectRow = computed(() => canDeleteProject(currentUser.value))
const PROJECT_TREE_INDENT = 24
const projectTree = computed(() => buildProjectTree(projects.value))
const enabledWorkflowSchemes = computed(() => (
  workflowSchemes.value.filter((item) => item.lifecycle_status === 'enabled')
))
function collectDescendantIds(projectId) {
  const ids = new Set()
  const walk = (pid) => {
    projects.value.filter(p => p.parent_id === pid).forEach(p => { ids.add(p.id); walk(p.id) })
  }
  walk(projectId)
  return ids
}
const parentProjectOptions = computed(() => {
  if (!editingId.value) return projects.value
  const excludeIds = collectDescendantIds(editingId.value)
  excludeIds.add(editingId.value)
  return projects.value.filter((item) => !excludeIds.has(item.id))
})
const {
  page: projectPage,
  pageSize: projectPageSize,
  pageSizes: projectPageSizes,
  total: projectTotal,
  pagedItems: pagedProjectTree
} = usePagination(projectTree)
const form = reactive({ parent_id: null, program_id: null, name: '', owner_id: null, assignee_rule_config_id: null, start_date: null, end_date: null, is_long_term: false, description: '' })
const statusActionOptions = {
  start: '启动',
  suspend: '挂起',
  close: '关闭',
  activate: '激活'
}
const statusForm = reactive({ effective_time: '', remark: '' })

const statusDialogTitle = computed(() => `${statusActionLabel(statusAction.value)}项目 ${statusTarget.value?.name || ''}`)
const statusConfirmText = computed(() => `${statusActionLabel(statusAction.value)}项目`)
const statusDateRequired = computed(() => statusAction.value === 'close' || (statusAction.value === 'start' && hasProjectAction(statusTarget.value, 'start')))
const statusDateLabel = computed(() => (statusAction.value === 'start' ? '实际开始日期' : '实际完成日期'))

function statusActionLabel(value) {
  return statusActionOptions[value] || value || '-'
}

function workflowSchemeLabel(configId) {
  if (!configId) return '-'
  return workflowSchemes.value.find((item) => item.id === configId)?.name || `#${configId}`
}
function membersForProject(projectId) { return projectMembersById.value[projectId] || [] }
function canManageProjectRow(row) { return canManageProject(row, currentUser.value, membersForProject(row.id)) }
function hasProjectAction(row, actionKey) { return Boolean(row && (workflowTransitions.value[row.id] || []).some((item) => item.action_key === actionKey)) }

function resetForm() {
  Object.assign(form, { parent_id: null, program_id: null, name: '', owner_id: null, assignee_rule_config_id: null, start_date: null, end_date: null, is_long_term: false, description: '' })
}

function buildProjectTree(items) {
  const nodes = items.map((item) => ({ ...item, children: [] }))
  const byId = new Map(nodes.map((item) => [item.id, item]))
  const roots = []
  for (const node of nodes) {
    if (node.parent_id && byId.has(node.parent_id)) byId.get(node.parent_id).children.push(node)
    else roots.push(node)
  }
  assignProjectTreeDepth(roots)
  return roots
}

function assignProjectTreeDepth(nodes, depth = 0) {
  nodes.forEach((node) => {
    node.tree_depth = depth
    assignProjectTreeDepth(node.children || [], depth + 1)
  })
}

function projectNameIndentStyle(row) {
  return { paddingLeft: `${(row.tree_depth || 0) * PROJECT_TREE_INDENT}px` }
}

function openCreate(parent = null) {
  editingId.value = null
  resetForm()
  if (parent) {
    form.parent_id = parent.id
    form.program_id = parent.program_id || null
  }
  dialogVisible.value = true
}
function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, { ...row, is_long_term: Boolean(row.is_long_term), description: row.description || '' })
  dialogVisible.value = true
}

function formatDateTime(value) {
  if (!value) return '-'
  return value.replace('T', ' ').slice(0, 19)
}

function currentDateTimeValue() {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}T${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`
}

async function openStatusDialog(row, action) {
  statusTarget.value = row
  statusAction.value = action
  Object.assign(statusForm, { effective_time: statusDateRequired.value ? currentDateTimeValue() : '', remark: '' })
  try {
    const response = await fetchProjectStatusOperations(row.id)
    statusHistory.value = response.data
    statusDialogVisible.value = true
  } catch {
    ElMessage.error('状态历史加载失败')
  }
}

async function loadData() {
  loading.value = true
  try {
    try {
      const [projectRes, programRes, userRes, workflowSchemeRes] = await Promise.all([
        fetchProjects(),
        fetchPrograms(),
        fetchUsers(),
        fetchAssigneeRuleConfigs()
      ])
      projects.value = projectRes.data
      programs.value = programRes.data
      users.value = userRes.data
      workflowSchemes.value = workflowSchemeRes.data
    } catch {
      ElMessage.error('项目列表加载失败')
      return
    }
    await Promise.all([loadProjectMembers(), loadProjectWorkflowTransitions()])
  } finally {
    loading.value = false
  }
}

async function loadProjectWorkflowTransitions() {
  try {
    await replaceWorkflowTransitionMap(
      fetchWorkflowTransitionsBatch,
      projects.value.map((item) => item.id),
      (value) => { workflowTransitions.value = value }
    )
  } catch {
    ElMessage.error('项目动作加载失败')
  }
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

async function submitProject() {
  if (!form.name.trim()) return ElMessage.warning('请填写项目名称')
  saving.value = true
  try {
    const payload = { ...form, program_id: form.program_id || null, owner_id: form.owner_id || null, assignee_rule_config_id: form.assignee_rule_config_id || null, end_date: form.is_long_term ? null : form.end_date }
    if (editingId.value) await updateProject(editingId.value, payload)
    else await createProject(payload)
    dialogVisible.value = false
    await loadData()
  } catch (error) {
    showActionError(error, editingId.value ? '项目保存失败' : '项目创建失败')
  } finally {
    saving.value = false
  }
}

async function changeProjectStatus(id, action) {
  const actions = {
    start: startProject,
    suspend: suspendProject,
    close: closeProject,
    activate: activateProject
  }
  try {
    await actions[action](id, buildStatusPayload())
    await loadData()
  } catch (error) {
    showActionError(error, '项目状态更新失败')
    throw error
  }
}

async function submitStatusOperation() {
  if (statusDateRequired.value && !statusForm.effective_time) return ElMessage.warning(`请选择${statusDateLabel.value}`)
  saving.value = true
  try {
    await changeProjectStatus(statusTarget.value.id, statusAction.value)
    statusDialogVisible.value = false
  } finally {
    saving.value = false
  }
}

function buildStatusPayload() {
  const payload = { remark: statusForm.remark }
  if (statusDateRequired.value) payload.effective_time = statusForm.effective_time
  return payload
}

async function removeProject(id) {
  try {
    await deleteProject(id)
    await loadData()
  } catch (error) {
    showActionError(error, '项目删除失败')
  }
}
onMounted(loadData)
</script>
