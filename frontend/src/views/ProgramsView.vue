<template>
  <section>
    <div class="page-head">
      <div>
        <h1>项目集</h1>
        <p>项目集以树状结构展示；展开项目集可查看子项目集和已绑定项目。</p>
      </div>
      <el-button type="primary" @click="openCreate()">新增项目集</el-button>
    </div>

    <el-card shadow="never">
      <el-table
        v-loading="loading"
        :data="pagedTreeRows"
        row-key="treeKey"
        default-expand-all
        stripe
        show-overflow-tooltip
        :tree-props="{ children: 'children' }"
      >
        <el-table-column prop="name" label="名称" min-width="180">
          <template #default="{ row }">
            <el-button
              v-if="row.nodeType === 'project'"
              class="project-row-link"
              link
              type="primary"
              @click="goToProject(row.id)"
            >
              {{ row.name }}
            </el-button>
            <span v-else>{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" min-width="90">
          <template #default="{ row }">
            <el-tag v-if="row.nodeType === 'program'" type="primary">项目集</el-tag>
            <el-tag v-else type="success">项目</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="负责人" min-width="120">
          <template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template>
        </el-table-column>
        <el-table-column label="计划开始" min-width="120">
          <template #default="{ row }">{{ row.nodeType === 'program' ? row.planned_start_date : row.start_date }}</template>
        </el-table-column>
        <el-table-column label="计划结束" min-width="120">
          <template #default="{ row }">{{ row.is_long_term ? '长期' : row.nodeType === 'program' ? row.planned_end_date : row.end_date }}</template>
        </el-table-column>
        <el-table-column prop="actual_start_date" label="实际开始" min-width="120" />
        <el-table-column prop="actual_end_date" label="实际结束" min-width="120" />
        <el-table-column label="状态" min-width="90">
          <template #default="{ row }">{{ statusLabel(row) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="330" fixed="right">
          <template #default="{ row }">
            <template v-if="row.nodeType === 'program'">
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button v-if="row.status === 'planning' || row.status === 'paused'" link type="success" @click="openStatusDialog(row, 'program', 'start')">启动</el-button>
              <el-button v-if="row.status === 'active'" link type="warning" @click="openStatusDialog(row, 'program', 'suspend')">挂起</el-button>
              <el-button v-if="row.status === 'active' || row.status === 'paused'" link type="danger" @click="openStatusDialog(row, 'program', 'close')">关闭</el-button>
              <el-button v-if="row.status === 'closed'" link type="success" @click="openStatusDialog(row, 'program', 'activate')">激活</el-button>
              <el-button link type="success" @click="openCreate(row.id)">新增项目集</el-button>
              <el-popconfirm title="确认删除该项目集？" @confirm="removeProgram(row.id)">
                <template #reference><el-button link type="danger">删除</el-button></template>
              </el-popconfirm>
            </template>
            <template v-else>
              <el-button link type="primary" @click="openProjectEdit(row.id)">编辑</el-button>
              <el-button v-if="row.status === 'planning' || row.status === 'paused'" link type="success" @click="openStatusDialog(row, 'project', 'start')">启动</el-button>
              <el-button v-if="row.status === 'active'" link type="warning" @click="openStatusDialog(row, 'project', 'suspend')">挂起</el-button>
              <el-button v-if="row.status === 'active' || row.status === 'paused'" link type="danger" @click="openStatusDialog(row, 'project', 'close')">关闭</el-button>
              <el-button v-if="row.status === 'closed'" link type="success" @click="openStatusDialog(row, 'project', 'activate')">激活</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-pagination">
        <el-pagination
          v-model:current-page="treePage"
          v-model:page-size="treePageSize"
          :page-sizes="treePageSizes"
          :total="treeTotal"
          layout="total, sizes, prev, pager, next, jumper"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px">
      <el-form label-position="top">
        <el-form-item label="项目集名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="form.owner_id" clearable filterable placeholder="请选择负责人">
            <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
          </el-select>
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="计划开始">
            <el-date-picker v-model="form.planned_start_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="计划结束">
            <div class="end-date-field">
              <el-checkbox v-model="form.is_long_term">长期</el-checkbox>
              <el-date-picker
                v-model="form.planned_end_date"
                value-format="YYYY-MM-DD"
                type="date"
                :disabled="form.is_long_term"
              />
            </div>
          </el-form-item>
          <el-form-item label="实际开始">
            <el-date-picker v-model="form.actual_start_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="实际结束">
            <el-date-picker v-model="form.actual_end_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
        </div>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitProgram">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="projectDialogVisible" title="编辑项目" width="560px">
      <el-form label-position="top">
        <el-form-item label="项目名称" required><el-input v-model="projectForm.name" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="上级项目">
            <el-select v-model="projectForm.parent_id" clearable filterable placeholder="请选择上级项目">
              <el-option v-for="item in flatProjects" :key="item.id" :label="item.name" :value="item.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="所属项目集">
            <el-select v-model="projectForm.program_id" clearable filterable placeholder="请选择项目集">
              <el-option v-for="program in flatPrograms" :key="program.id" :label="program.name" :value="program.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="负责人">
            <el-select v-model="projectForm.owner_id" clearable filterable placeholder="请选择负责人">
              <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="开始日期">
            <el-date-picker v-model="projectForm.start_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="结束日期">
            <div class="end-date-field">
              <el-checkbox v-model="projectForm.is_long_term">长期</el-checkbox>
              <el-date-picker
                v-model="projectForm.end_date"
                value-format="YYYY-MM-DD"
                type="date"
                :disabled="projectForm.is_long_term"
              />
            </div>
          </el-form-item>
          <el-form-item label="实际开始">
            <el-date-picker v-model="projectForm.actual_start_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="实际结束">
            <el-date-picker v-model="projectForm.actual_end_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
        </div>
        <el-form-item label="描述"><el-input v-model="projectForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="projectDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitProject">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="statusDialogVisible" :title="statusDialogTitle" width="760px" class="status-operation-dialog">
      <el-form label-position="top">
        <el-form-item label="实际完成" required>
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
              <el-tag size="small" effect="plain">{{ statusLabel(item) }}</el-tag>
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
import { useRouter } from 'vue-router'

import {
  activateProgram,
  closeProgram,
  createProgram,
  deleteProgram,
  fetchProgramStatusOperations,
  fetchProgramStatusOptions,
  fetchProgramTree,
  startProgram,
  suspendProgram,
  updateProgram
} from '../api/programs'
import {
  activateProject,
  closeProject,
  fetchProject,
  fetchProjectStatusOperations,
  startProject,
  suspendProject,
  updateProject
} from '../api/projects'
import { fetchUsers } from '../api/users'
import { userLabel } from '../utils/referenceLabels'
import { usePagination } from '../utils/usePagination'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const projectDialogVisible = ref(false)
const statusDialogVisible = ref(false)
const editingId = ref(null)
const projectEditingId = ref(null)
const statusTarget = ref(null)
const statusTargetType = ref('')
const statusAction = ref('')
const statusHistory = ref([])
const programTree = ref([])
const statusOptions = ref([])
const users = ref([])
const projectStatusOptions = [
  { label: '规划中', value: 'planning' },
  { label: '进行中', value: 'active' },
  { label: '已挂起', value: 'paused' },
  { label: '已关闭', value: 'closed' }
]
const statusActionOptions = {
  start: '启动',
  suspend: '挂起',
  close: '关闭',
  activate: '激活'
}
const form = reactive({
  parent_id: null,
  name: '',
  owner_id: null,
  planned_start_date: null,
  planned_end_date: null,
  actual_start_date: null,
  actual_end_date: null,
  is_long_term: false,
  status: 'planning',
  description: ''
})
const projectForm = reactive({
  parent_id: null,
  program_id: null,
  name: '',
  owner_id: null,
  start_date: null,
  end_date: null,
  actual_start_date: null,
  actual_end_date: null,
  is_long_term: false,
  status: 'planning',
  description: ''
})
const statusForm = reactive({ effective_time: '', remark: '' })

const dialogTitle = computed(() => {
  if (editingId.value) return '编辑项目集'
  return '新增项目集'
})
const statusTargetLabel = computed(() => (statusTargetType.value === 'program' ? '项目集' : '项目'))
const statusDialogTitle = computed(() => `${statusActionLabel(statusAction.value)}${statusTargetLabel.value} ${statusTarget.value?.name || ''}`)
const statusConfirmText = computed(() => `${statusActionLabel(statusAction.value)}${statusTargetLabel.value}`)

const treeRows = computed(() => programTree.value.map(toTreeRow))
const flatPrograms = computed(() => flattenPrograms(programTree.value))
const flatProjects = computed(() => flattenProjects(programTree.value).filter((item) => item.id !== projectEditingId.value))
const {
  page: treePage,
  pageSize: treePageSize,
  pageSizes: treePageSizes,
  total: treeTotal,
  pagedItems: pagedTreeRows
} = usePagination(treeRows)

function statusLabel(row) {
  const options = row.nodeType === 'program' ? statusOptions.value : projectStatusOptions
  if ('from_status' in row || 'to_status' in row) {
    return `${statusValueLabel(row.from_status)} → ${statusValueLabel(row.to_status)}`
  }
  return options.find((option) => option.value === row.status)?.label || row.status || '-'
}

function statusValueLabel(value) {
  return [...statusOptions.value, ...projectStatusOptions].find((option) => option.value === value)?.label || value || '-'
}

function statusActionLabel(value) {
  return statusActionOptions[value] || value || '-'
}

function toTreeRow(node) {
  return {
    ...node,
    treeKey: `program-${node.id}`,
    nodeType: 'program',
    children: [
      ...(node.children || []).map(toTreeRow),
      ...(node.projects || []).map((project) => ({
        ...project,
        treeKey: `project-${project.id}`,
        nodeType: 'project',
        program_id: node.id,
        children: []
      }))
    ]
  }
}

function flattenPrograms(nodes) {
  return nodes.flatMap((node) => [
    { id: node.id, name: node.name },
    ...flattenPrograms(node.children || [])
  ])
}

function flattenProjects(nodes) {
  return nodes.flatMap((node) => [
    ...(node.projects || []).map((project) => ({ id: project.id, name: project.name })),
    ...flattenProjects(node.children || [])
  ])
}

function resetForm(parentId = null) {
  Object.assign(form, {
    parent_id: parentId,
    name: '',
    owner_id: null,
    planned_start_date: null,
    planned_end_date: null,
    actual_start_date: null,
    actual_end_date: null,
    is_long_term: false,
    status: 'planning',
    description: ''
  })
}

function openCreate(parentId = null) {
  editingId.value = null
  resetForm(parentId)
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    parent_id: row.parent_id,
    name: row.name,
    owner_id: row.owner_id,
    planned_start_date: row.planned_start_date || null,
    planned_end_date: row.planned_end_date || null,
    actual_start_date: row.actual_start_date || null,
    actual_end_date: row.actual_end_date || null,
    is_long_term: Boolean(row.is_long_term),
    status: row.status,
    description: row.description || ''
  })
  dialogVisible.value = true
}

function goToProject(projectId) {
  router.push({ name: 'project-detail', params: { id: projectId } })
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

function resetProjectForm() {
  Object.assign(projectForm, {
    parent_id: null,
    program_id: null,
    name: '',
    owner_id: null,
    start_date: null,
    end_date: null,
    actual_start_date: null,
    actual_end_date: null,
    is_long_term: false,
    status: 'planning',
    description: ''
  })
}

async function openProjectEdit(projectId) {
  projectEditingId.value = projectId
  resetProjectForm()
  try {
    const response = await fetchProject(projectId)
    Object.assign(projectForm, {
      ...response.data,
      is_long_term: Boolean(response.data.is_long_term),
      description: response.data.description || ''
    })
    projectDialogVisible.value = true
  } catch {
    ElMessage.error('项目详情加载失败')
  }
}

async function openStatusDialog(row, targetType, action) {
  statusTarget.value = row
  statusTargetType.value = targetType
  statusAction.value = action
  Object.assign(statusForm, { effective_time: currentDateTimeValue(), remark: '' })
  try {
    const response =
      targetType === 'program'
        ? await fetchProgramStatusOperations(row.id)
        : await fetchProjectStatusOperations(row.id)
    statusHistory.value = response.data
    statusDialogVisible.value = true
  } catch {
    ElMessage.error('状态历史加载失败')
  }
}

async function loadData() {
  loading.value = true
  try {
    const [treeRes, statusRes, userRes] = await Promise.all([fetchProgramTree(), fetchProgramStatusOptions(), fetchUsers()])
    programTree.value = treeRes.data
    statusOptions.value = statusRes.data
    users.value = userRes.data
  } catch {
    ElMessage.error('项目集树加载失败')
  } finally {
    loading.value = false
  }
}

async function submitProgram() {
  if (!form.name.trim()) return ElMessage.warning('请填写项目集名称')
  saving.value = true
  try {
    const payload = {
      ...form,
      parent_id: form.parent_id || null,
      owner_id: form.owner_id || null,
      planned_end_date: form.is_long_term ? null : form.planned_end_date
    }
    delete payload.status
    if (editingId.value) await updateProgram(editingId.value, payload)
    else await createProgram(payload)
    dialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}

async function changeProgramStatus(id, action, payload = {}) {
  const actions = {
    start: startProgram,
    suspend: suspendProgram,
    close: closeProgram,
    activate: activateProgram
  }
  try {
    await actions[action](id, payload)
    await loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '项目集状态更新失败')
    throw error
  }
}

async function submitProject() {
  if (!projectForm.name.trim()) return ElMessage.warning('请填写项目名称')
  saving.value = true
  try {
    const payload = {
      ...projectForm,
      program_id: projectForm.program_id || null,
      owner_id: projectForm.owner_id || null,
      end_date: projectForm.is_long_term ? null : projectForm.end_date
    }
    delete payload.status
    await updateProject(projectEditingId.value, payload)
    projectDialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}

async function changeProjectStatus(id, action, payload = {}) {
  const actions = {
    start: startProject,
    suspend: suspendProject,
    close: closeProject,
    activate: activateProject
  }
  try {
    await actions[action](id, payload)
    await loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '项目状态更新失败')
    throw error
  }
}

async function submitStatusOperation() {
  if (!statusForm.effective_time) return ElMessage.warning('请选择实际完成时间')
  saving.value = true
  const payload = {
    effective_time: statusForm.effective_time,
    remark: statusForm.remark
  }
  try {
    if (statusTargetType.value === 'program') {
      await changeProgramStatus(statusTarget.value.id, statusAction.value, payload)
    } else {
      await changeProjectStatus(statusTarget.value.id, statusAction.value, payload)
    }
    statusDialogVisible.value = false
  } finally {
    saving.value = false
  }
}

async function removeProgram(id) {
  await deleteProgram(id)
  await loadData()
}

onMounted(loadData)
</script>
