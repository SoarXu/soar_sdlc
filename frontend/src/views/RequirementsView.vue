<template>
  <section>
    <div class="page-head">
      <div>
        <h1>需求</h1>
        <p>维护需求并生成任务，关联项目、迭代和人员均以名称展示。</p>
      </div>
      <div class="page-actions">
        <el-button v-if="canCreateAnyRequirement" @click="openImportDialog">导入需求</el-button>
        <el-button v-if="canCreateAnyRequirement" type="primary" @click="openCreate">新增需求</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="pagedRequirements" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="需求标题" width="160" show-overflow-tooltip />
        <el-table-column label="项目" width="180"><template #default="{ row }">{{ labelById(projects, row.project_id) }}</template></el-table-column>
        <el-table-column label="来源项目" width="180"><template #default="{ row }">{{ labelById(projects, row.source_project_id) }}</template></el-table-column>
        <el-table-column label="迭代" width="160"><template #default="{ row }">{{ labelById(iterations, row.iteration_id) }}</template></el-table-column>
        <el-table-column label="当前处理人" width="150"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column label="优先级" width="100"><template #default="{ row }"><RequirementPriorityBadge :value="row.priority" /></template></el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tooltip v-if="closeReasonByRequirement[row.id]" :content="closeReasonByRequirement[row.id]" placement="top" raw-content>
              <span class="status-with-reason">{{ row.status_name || '-' }}</span>
            </el-tooltip>
            <span v-else>{{ row.status_name || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" :width="workflowOperationWidth" fixed="right">
          <template #default="{ row }">
            <WatchToggleButton object-type="requirement" :object-id="row.id" />
            <WorkflowActionButtons object-type="requirement" :object-id="row.id" mode="list" :transitions="workflowTransitionsFor(row)" :auto-load="false" :users="users" @command="handleWorkflowCommand(row, $event)" @executed="loadData" /><el-button v-if="canGenerateTask(row)" link type="success" @click="openGenerate(row)">生成任务</el-button>
            <el-popconfirm v-if="canDeleteRequirement(row)" title="确认删除该需求？" @confirm="removeRequirement(row.id)">
              <template #reference><el-button link type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-pagination">
        <el-pagination
          v-model:current-page="requirementPage"
          v-model:page-size="requirementPageSize"
          :page-sizes="requirementPageSizes"
          :total="requirementTotal"
          layout="total, sizes, prev, pager, next, jumper"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑需求' : '新增需求'" width="640px">
      <el-form label-position="top">
        <el-form-item label="需求标题" required><el-input v-model="form.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目" required>
            <el-select v-model="form.project_id" filterable placeholder="请选择项目">
              <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="来源项目">
            <el-select v-model="form.source_project_id" clearable filterable placeholder="请选择来源项目" @change="onSourceProjectChange">
              <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="迭代">
            <el-select v-model="form.iteration_id" clearable filterable placeholder="请选择迭代">
              <el-option v-for="iteration in iterations" :key="iteration.id" :label="iteration.name" :value="iteration.id" />
            </el-select>
          </el-form-item>
          <el-form-item v-if="!editingId" label="当前处理人">
            <el-select v-model="form.owner_id" clearable filterable placeholder="请选择当前处理人" @change="onOwnerChange">
              <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="提出人">
            <el-select v-model="form.proposer_id" clearable filterable placeholder="请选择提出人">
              <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
            </el-select>
          </el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="类型">
            <el-select v-model="form.requirement_type">
              <el-option v-for="option in requirementTypeOptions" :key="option" :label="option" :value="option" />
            </el-select>
          </el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="form.priority" class="priority-select">
              <template #prefix><RequirementPriorityBadge :value="form.priority" /></template>
              <el-option v-for="option in requirementPriorityOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option>
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="需求描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="验收标准"><el-input v-model="form.acceptance_criteria" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRequirement">保存</el-button></template>
    </el-dialog>

    <RequirementEditDialog v-model="editDialogVisible" :item-id="editingId" @saved="loadData" />

    <el-dialog v-model="generateVisible" title="从需求生成任务" width="480px">
      <el-form label-position="top">
        <el-form-item label="任务标题" required><el-input v-model="generateForm.title" /></el-form-item>
        <el-form-item label="任务分支"><el-select v-model="generateForm.task_type" disabled><el-option v-for="option in TASK_BRANCH_OPTIONS" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
        <el-form-item label="描述"><el-input v-model="generateForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="generateVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitGenerateTask">生成</el-button></template>
    </el-dialog>

    

    <el-dialog v-model="importVisible" title="导入需求" width="720px">
      <div class="import-template-action">
        <span>请先下载固定模板，填写后上传 Excel 文件。</span>
        <el-button link type="primary" @click="downloadImportTemplate">下载模板</el-button>
      </div>
      <el-upload
        :auto-upload="false"
        :limit="1"
        accept=".xlsx"
        :on-change="onImportFileChange"
        :on-remove="clearImportFile"
      >
        <el-button>选择 Excel 文件</el-button>
      </el-upload>

      <div v-if="importPreview" class="import-preview">
        <p class="import-preview-summary">
          有效 {{ importPreview.valid_count }} 行，失败 {{ importPreview.error_count }} 行，重复 {{ importPreview.duplicate_count }} 行
        </p>
        <el-table v-if="importPreview.errors.length" :data="importPreview.errors" size="small" border>
          <el-table-column prop="row_number" label="行号" width="80" />
          <el-table-column label="错误">
            <template #default="{ row }">{{ row.messages.join('；') }}</template>
          </el-table-column>
        </el-table>
        <template v-if="importPreview.duplicates.length">
          <div class="import-strategy">
            <el-radio-group v-model="duplicateStrategy">
              <el-radio label="update_existing">更新已有需求</el-radio>
              <el-radio label="create_duplicate">重复创建</el-radio>
            </el-radio-group>
          </div>
          <el-table :data="importPreview.duplicates" size="small" border>
            <el-table-column prop="row_number" label="行号" width="80" />
            <el-table-column prop="project_name" label="项目" min-width="140" />
            <el-table-column prop="title" label="需求标题" min-width="160" />
            <el-table-column prop="existing_requirement_id" label="已有ID" width="90" />
            <el-table-column prop="existing_requirement_title" label="已有需求" min-width="160" />
          </el-table>
        </template>
      </div>

      <template #footer>
        <el-button @click="importVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitImportPreview">预检</el-button>
        <el-button
          v-if="importPreview && !importPreview.error_count && importPreview.duplicate_count"
          type="success"
          :loading="saving"
          @click="submitImportCommit()"
        >
          确认导入
        </el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { fetchIterations } from '../api/iterations'
import { fetchProjectMembers, fetchProjects } from '../api/projects'
import {
  commitRequirementImport,
  createRequirement,
  deleteRequirement,
  downloadRequirementImportTemplate,
  fetchRequirements,
  fetchRequirementStatusOperations,
  previewRequirementImport,
  updateRequirement
} from '../api/requirements'
import { createLinkedTask } from '../api/tasks'
import { fetchUsers } from '../api/users'
import { fetchWorkflowTransitionsBatch } from '../api/workflowRuntime'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import WatchToggleButton from '../components/WatchToggleButton.vue'
import WorkflowActionButtons from '../components/WorkflowActionButtons.vue'
import RequirementEditDialog from '../components/work-items/RequirementEditDialog.vue'
import { showActionError } from '../utils/actionFeedback'
import { currentUserId } from '../utils/currentUser'
import { loadCloseReasonMap } from '../utils/closeReasonTooltip'
import { canCreateWorkItem, canDeleteWorkItem, canExecuteWorkItem, currentUserFromStorage } from '../utils/permissions'
import { labelById, userLabel } from '../utils/referenceLabels'
import { usePagination } from '../utils/usePagination'
import { workflowActionColumnWidth } from '../utils/workflowActionColumn'
import { TASK_BRANCH_OPTIONS } from '../utils/taskBranchRules'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editDialogVisible = ref(false)
const generateVisible = ref(false)
const importVisible = ref(false)
const editingId = ref(null)
const generatingRequirementId = ref(null)
const requirements = ref([])
const closeReasonByRequirement = ref({})
const workflowTransitions = ref({})
const projects = ref([])
const projectMembersById = ref({})
const iterations = ref([])
const users = ref([])
const currentUser = computed(() => currentUserFromStorage(users.value))
const canCreateAnyRequirement = computed(() => projects.value.some((project) => canCreateWorkItem(project, currentUser.value, membersForProject(project.id))))
const {
  page: requirementPage,
  pageSize: requirementPageSize,
  pageSizes: requirementPageSizes,
  total: requirementTotal,
  pagedItems: pagedRequirements
} = usePagination(requirements)
const workflowOperationWidth = computed(() => workflowActionColumnWidth(
  pagedRequirements.value.map((row) => workflowTransitionsFor(row)),
  { minWidth: 220, extraWidth: 150 }
))
const form = reactive({ project_id: null, source_project_id: null, iteration_id: null, title: '', requirement_type: '功能', priority: '3', owner_id: null, proposer_id: null, description: '', acceptance_criteria: '' })
const ownerManuallySet = ref(false)
const generateForm = reactive({ title: '', task_type: 'requirement_implementation', description: '' })
const importFile = ref(null)
const importPreview = ref(null)
const duplicateStrategy = ref('')
const requirementPriorityOptions = [
  { label: '1', value: '1' },
  { label: '2', value: '2' },
  { label: '3', value: '3' },
  { label: '4', value: '4' },
  { label: '5', value: '5' }
]
const requirementTypeOptions = ['功能', '接口', '性能', '安全', '体验', '改进', '其他']
const legacyRequirementPriorityValues = { high: '1', medium: '3', low: '5' }

function normalizeRequirementPriority(value) { return legacyRequirementPriorityValues[value] || value || '3' }
function isRequirementProjectClosed(row) { return projects.value.find((item) => item.id === row.project_id)?.state_category === 'terminal' }
function workflowTransitionsFor(row) { return workflowTransitions.value[`requirement:${row.id}`] || [] }
function projectForRequirement(row) { return projects.value.find((item) => item.id === row.project_id) || null }
function membersForProject(projectId) { return projectMembersById.value[projectId] || [] }
function canGenerateTask(row) {
  const project = projectForRequirement(row)
  return !isRequirementProjectClosed(row) && canExecuteWorkItem(row, currentUser.value, project, membersForProject(project?.id))
}
function canDeleteRequirement(row) {
  const project = projectForRequirement(row)
  return !isRequirementProjectClosed(row) && canDeleteWorkItem(project, currentUser.value, membersForProject(project?.id))
}
function resetForm() { Object.assign(form, { project_id: null, source_project_id: null, iteration_id: null, title: '', requirement_type: '功能', priority: '3', owner_id: null, proposer_id: currentUserId(users.value), description: '', acceptance_criteria: '' }); ownerManuallySet.value = false }
function openCreate() { editingId.value = null; resetForm(); dialogVisible.value = true }
function onSourceProjectChange() {}
function onOwnerChange() { ownerManuallySet.value = true }
function openEdit(row) { editingId.value = row.id; editDialogVisible.value = true }
function handleWorkflowCommand(row, { commandType }) {
  if (commandType === 'edit') openEdit(row)
  if (commandType === 'view_history') router.push(`/requirements/${row.id}#history`)
}
function openGenerate(row) { generatingRequirementId.value = row.id; generateForm.title = row.title; generateForm.task_type = 'requirement_implementation'; generateForm.description = ''; generateVisible.value = true }

async function downloadImportTemplate() {
  const response = await downloadRequirementImportTemplate()
  const url = URL.createObjectURL(response.data)
  const link = document.createElement('a')
  link.href = url
  link.download = 'requirements-template.xlsx'
  link.click()
  URL.revokeObjectURL(url)
}

function openImportDialog() {
  importFile.value = null
  importPreview.value = null
  duplicateStrategy.value = ''
  importVisible.value = true
}

function onImportFileChange(file) {
  importFile.value = file.raw
  importPreview.value = null
  duplicateStrategy.value = ''
}

function clearImportFile() {
  importFile.value = null
  importPreview.value = null
  duplicateStrategy.value = ''
}

async function loadData() {
  loading.value = true
  try {
    const [reqRes, projectRes, iterationRes, userRes] = await Promise.all([fetchRequirements(), fetchProjects(), fetchIterations(), fetchUsers()])
    requirements.value = reqRes.data
    projects.value = projectRes.data
    iterations.value = iterationRes.data
    users.value = userRes.data
    await loadProjectMembers()
    closeReasonByRequirement.value = await loadCloseReasonMap(requirements.value, fetchRequirementStatusOperations)
    await loadWorkflowTransitions()
  } catch {
    ElMessage.error('????????')
  } finally {
    loading.value = false
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

async function loadWorkflowTransitions() {
  if (!requirements.value.length) {
    workflowTransitions.value = {}
    return
  }
  const { data } = await fetchWorkflowTransitionsBatch(requirements.value.map((item) => ({ object_type: 'requirement', id: item.id })))
  workflowTransitions.value = Object.fromEntries((data.items || []).map((item) => [`${item.object_type}:${item.id}`, item.transitions || []]))
}

async function submitRequirement() {
  if (!form.project_id || !form.title.trim()) return ElMessage.warning('????????????')
  saving.value = true
  try {
    const { status: _status, ...formData } = form
    const payload = { ...formData, iteration_id: form.iteration_id || null, owner_id: form.owner_id || null, proposer_id: form.proposer_id || null }
    if (editingId.value) await updateRequirement(editingId.value, payload); else await createRequirement(payload)
    dialogVisible.value = false
    await loadData()
  } catch (error) {
    showActionError(error, editingId.value ? '需求保存失败' : '需求创建失败')
  } finally {
    saving.value = false
  }
}

async function submitGenerateTask() {
  if (!generateForm.title.trim()) return ElMessage.warning('???????')
  saving.value = true
  try {
    await createLinkedTask({
      source_type: 'requirement',
      source_id: generatingRequirementId.value,
      ...generateForm
    })
    generateVisible.value = false
    ElMessage.success('?????')
    await loadData()
  } catch (error) {
    showActionError(error, '任务生成失败')
  } finally {
    saving.value = false
  }
}

async function submitImportPreview() {
  if (!importFile.value) return ElMessage.warning('??? Excel ??')
  saving.value = true
  try {
    const { data } = await previewRequirementImport(importFile.value)
    importPreview.value = data
    if (data.error_count) return
    if (!data.duplicate_count) await submitImportCommit('create_duplicate')
  } catch (error) {
    showActionError(error, '导入预览失败')
  } finally {
    saving.value = false
  }
}

async function submitImportCommit(strategy = duplicateStrategy.value) {
  if (!importFile.value) return ElMessage.warning('??? Excel ??')
  if (importPreview.value?.duplicate_count && !strategy) return ElMessage.warning('?????????')
  saving.value = true
  try {
    const { data } = await commitRequirementImport(importFile.value, strategy || 'create_duplicate')
    importVisible.value = false
    await loadData()
    ElMessage.success(`??????? ${data.created_count} ???? ${data.updated_count} ?`)
  } catch (error) {
    showActionError(error, '导入需求失败')
  } finally {
    saving.value = false
  }
}
async function removeRequirement(id) {
  try {
    await deleteRequirement(id)
    await loadData()
  } catch (error) {
    showActionError(error, '需求删除失败')
  }
}
onMounted(loadData)
</script>
