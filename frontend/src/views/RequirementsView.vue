<template>
  <section>
    <div class="page-head">
      <div>
        <h1>需求</h1>
        <p>维护需求并生成任务，关联项目、迭代和人员均以名称展示。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增需求</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="pagedRequirements" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="需求标题" width="160" show-overflow-tooltip />
        <el-table-column label="项目" width="180"><template #default="{ row }">{{ labelById(projects, row.project_id) }}</template></el-table-column>
        <el-table-column label="来源项目" width="180"><template #default="{ row }">{{ labelById(projects, row.source_project_id) }}</template></el-table-column>
        <el-table-column label="迭代" width="160"><template #default="{ row }">{{ labelById(iterations, row.iteration_id) }}</template></el-table-column>
        <el-table-column label="负责人" width="150"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column label="优先级" width="100"><template #default="{ row }"><RequirementPriorityBadge :value="row.priority" /></template></el-table-column>
        <el-table-column prop="review_status" label="评审状态" width="120" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tooltip v-if="closeReasonByRequirement[row.id]" :content="closeReasonByRequirement[row.id]" placement="top" raw-content>
              <span class="status-with-reason">{{ requirementStatusLabel(row.status) }}</span>
            </el-tooltip>
            <span v-else>{{ requirementStatusLabel(row.status) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="280" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" :disabled="isRequirementProjectClosed(row)" @click="openEdit(row)">编辑</el-button>
            <el-button v-if="canActivateRequirement(row)" link type="warning" @click="activateRequirementRow(row.id)">激活</el-button>
            <el-button v-if="row.status === 'active'" link type="danger" @click="openClose(row)">关闭</el-button>
            <el-button link type="success" @click="openGenerate(row)">生成任务</el-button>
            <el-popconfirm title="确认删除该需求？" :disabled="isRequirementProjectClosed(row)" @confirm="removeRequirement(row.id)">
              <template #reference><el-button link type="danger" :disabled="isRequirementProjectClosed(row)">删除</el-button></template>
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
          <el-form-item label="负责人">
            <el-select v-model="form.owner_id" clearable filterable placeholder="请选择负责人" @change="onOwnerChange">
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
          <el-form-item label="评审状态">
            <el-select v-model="form.review_status">
              <el-option label="无需评审" value="not_required" /><el-option label="待评审" value="pending" /><el-option label="已通过" value="approved" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="需求描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="验收标准"><el-input v-model="form.acceptance_criteria" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRequirement">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="generateVisible" title="从需求生成任务" width="480px">
      <el-form label-position="top">
        <el-form-item label="任务标题" required><el-input v-model="generateForm.title" /></el-form-item>
        <el-form-item label="任务类型"><el-input v-model="generateForm.task_type" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="generateForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="generateVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitGenerateTask">生成</el-button></template>
    </el-dialog>

    <el-dialog v-model="closeVisible" title="关闭需求" width="480px">
      <el-form label-position="top">
        <el-form-item label="关闭原因" required>
          <el-select v-model="closeForm.reason" placeholder="请选择关闭原因">
            <el-option v-for="option in requirementCloseReasons" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="closeForm.remark" type="textarea" :rows="3" placeholder="补充说明本次关闭原因" />
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="closeVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitClose">确认关闭</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchIterations } from '../api/iterations'
import { fetchProjects } from '../api/projects'
import { activateRequirement, closeRequirement, createRequirement, deleteRequirement, fetchRequirements, fetchRequirementStatusOperations, generateTask, updateRequirement } from '../api/requirements'
import { fetchUsers } from '../api/users'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import { currentUserId } from '../utils/currentUser'
import { loadCloseReasonMap } from '../utils/closeReasonTooltip'
import { labelById, userLabel } from '../utils/referenceLabels'
import { usePagination } from '../utils/usePagination'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const generateVisible = ref(false)
const closeVisible = ref(false)
const editingId = ref(null)
const generatingRequirementId = ref(null)
const closingRequirementId = ref(null)
const requirements = ref([])
const closeReasonByRequirement = ref({})
const projects = ref([])
const iterations = ref([])
const users = ref([])
const {
  page: requirementPage,
  pageSize: requirementPageSize,
  pageSizes: requirementPageSizes,
  total: requirementTotal,
  pagedItems: pagedRequirements
} = usePagination(requirements)
const form = reactive({ project_id: null, source_project_id: null, iteration_id: null, title: '', requirement_type: '功能', priority: '3', owner_id: null, proposer_id: null, status: 'draft', review_status: 'not_required', description: '', acceptance_criteria: '', source_reviewed: false })
const ownerManuallySet = ref(false)
const generateForm = reactive({ title: '', task_type: '', description: '' })
const closeForm = reactive({ reason: '', remark: '' })
const requirementPriorityOptions = [
  { label: '1', value: '1' },
  { label: '2', value: '2' },
  { label: '3', value: '3' },
  { label: '4', value: '4' },
  { label: '5', value: '5' }
]
const requirementCloseReasons = ['已完成', '重复', '延期', '不做', '设计如此']
const requirementTypeOptions = ['功能', '接口', '性能', '安全', '体验', '改进', '其他']
const legacyRequirementPriorityValues = { high: '1', medium: '3', low: '5' }
const requirementStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '激活', value: 'active' },
  { label: '完成', value: 'done' },
  { label: '关闭', value: 'closed' }
]

function normalizeRequirementPriority(value) { return legacyRequirementPriorityValues[value] || value || '3' }
function requirementStatusLabel(value) { return requirementStatusOptions.find((option) => option.value === value)?.label || value || '-' }
function canActivateRequirement(row) { return ['draft', 'closed'].includes(row.status) }
function isRequirementProjectClosed(row) { return projects.value.find((item) => item.id === row.project_id)?.status === 'closed' }
function apiErrorMessage(error, fallback) { return error?.response?.data?.detail || fallback }
function showActionError(error, fallback) { ElMessageBox.alert(apiErrorMessage(error, fallback), '提示', { type: 'warning' }) }
function resetForm() { Object.assign(form, { project_id: null, source_project_id: null, iteration_id: null, title: '', requirement_type: '功能', priority: '3', owner_id: null, proposer_id: currentUserId(users.value), status: 'draft', review_status: 'not_required', description: '', acceptance_criteria: '', source_reviewed: false }); ownerManuallySet.value = false }
function openCreate() { editingId.value = null; resetForm(); dialogVisible.value = true }
function onSourceProjectChange(projectId) { if (!projectId || ownerManuallySet.value) return; const project = projects.value.find(p => p.id === projectId); if (project && project.owner_id) { form.owner_id = project.owner_id } }
function onOwnerChange() { ownerManuallySet.value = true }
function openEdit(row) { editingId.value = row.id; ownerManuallySet.value = true; Object.assign(form, { ...row, priority: normalizeRequirementPriority(row.priority), requirement_type: row.requirement_type || '', description: row.description || '', acceptance_criteria: row.acceptance_criteria || '' }); dialogVisible.value = true }
function openGenerate(row) { generatingRequirementId.value = row.id; generateForm.title = row.title; generateForm.task_type = 'development'; generateForm.description = ''; generateVisible.value = true }
function openClose(row) { closingRequirementId.value = row.id; Object.assign(closeForm, { reason: '', remark: '' }); closeVisible.value = true }

async function loadData() {
  loading.value = true
  try {
    const [reqRes, projectRes, iterationRes, userRes] = await Promise.all([fetchRequirements(), fetchProjects(), fetchIterations(), fetchUsers()])
    requirements.value = reqRes.data; projects.value = projectRes.data; iterations.value = iterationRes.data; users.value = userRes.data
    closeReasonByRequirement.value = await loadCloseReasonMap(requirements.value, fetchRequirementStatusOperations)
  } catch { ElMessage.error('需求列表加载失败') } finally { loading.value = false }
}

async function submitRequirement() {
  if (!form.project_id || !form.title.trim()) return ElMessage.warning('请选择项目并填写需求标题')
  saving.value = true
  try {
    const { status: _status, ...formData } = form
    const payload = { ...formData, iteration_id: form.iteration_id || null, owner_id: form.owner_id || null, proposer_id: form.proposer_id || null }
    if (editingId.value) await updateRequirement(editingId.value, payload); else await createRequirement(payload)
    dialogVisible.value = false; await loadData()
  } finally { saving.value = false }
}
async function submitGenerateTask() { if (!generateForm.title.trim()) return ElMessage.warning('请填写任务标题'); saving.value = true; try { await generateTask(generatingRequirementId.value, { ...generateForm }); generateVisible.value = false; ElMessage.success('任务已生成') } finally { saving.value = false } }
async function activateRequirementRow(id) {
  try {
    await activateRequirement(id)
    await loadData()
    ElMessage.success('需求已激活，关联任务已进入进行中')
  } catch (error) {
    showActionError(error, '需求激活失败')
  }
}
async function submitClose() {
  if (!closeForm.reason) return ElMessage.warning('请选择关闭原因')
  saving.value = true
  try {
    await closeRequirement(closingRequirementId.value, { ...closeForm })
    closeVisible.value = false
    await loadData()
    ElMessage.success('需求已关闭')
  } finally {
    saving.value = false
  }
}
async function removeRequirement(id) { await deleteRequirement(id); await loadData() }
onMounted(loadData)
</script>
