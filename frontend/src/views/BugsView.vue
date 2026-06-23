<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Bug</h1>
        <p>维护缺陷和关联上下文，项目、需求、任务、用例、测试单和人员均以名称选择。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增 Bug</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="pagedBugs" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="Bug 标题" min-width="220"><template #default="{ row }"><router-link class="table-link" :to="{ name: 'bug-detail', params: { id: row.id } }">{{ row.title }}</router-link></template></el-table-column>
        <el-table-column label="项目" width="170"><template #default="{ row }">{{ labelById(projects, row.project_id) }}</template></el-table-column>
        <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(requirements, row.requirement_id, 'title') }}</template></el-table-column>
        <el-table-column label="任务" width="180"><template #default="{ row }">{{ labelById(tasks, row.task_id, 'title') }}</template></el-table-column>
        <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column label="严重程度" width="110"><template #default="{ row }"><RequirementPriorityBadge :value="row.severity" /></template></el-table-column>
        <el-table-column label="状态" width="120"><template #default="{ row }">{{ bugStatusLabel(row.status) }}</template></el-table-column>
        <el-table-column label="操作" width="380" fixed="right">
          <template #default="{ row }">
            <div class="table-actions">
              <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
              <el-button v-if="['open', 'reopened', 'suspended'].includes(row.status)" link type="success" @click="openBugAction(row, 'start_fixing')">确认</el-button>
              <el-button v-if="row.status === 'fixing'" link type="success" @click="openBugAction(row, 'resolve')">解决</el-button>
              <el-button v-if="['verifying', 'closed'].includes(row.status)" link type="warning" @click="openBugAction(row, 'activate')">激活</el-button>
              <el-button v-if="['open', 'fixing', 'reopened'].includes(row.status)" link type="warning" @click="openBugAction(row, 'suspend')">挂起</el-button>
              <el-button v-if="['open', 'suspended', 'verifying'].includes(row.status)" link type="danger" @click="openBugAction(row, 'close')">关闭</el-button>
              <el-popconfirm title="确认删除该 Bug？" @confirm="removeBug(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm>
            </div>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-pagination">
        <el-pagination
          v-model:current-page="bugPage"
          v-model:page-size="bugPageSize"
          :page-sizes="bugPageSizes"
          :total="bugTotal"
          layout="total, sizes, prev, pager, next, jumper"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑 Bug' : '新增 Bug'" width="700px">
      <el-form label-position="top">
        <el-form-item label="Bug 标题" required><el-input v-model="form.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目" required><el-select v-model="form.project_id" filterable placeholder="请选择项目"><el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" /></el-select></el-form-item>
          <el-form-item label="需求"><el-select v-model="form.requirement_id" clearable filterable placeholder="请选择需求"><el-option v-for="requirement in requirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item>
          <el-form-item label="任务"><el-select v-model="form.task_id" clearable filterable placeholder="请选择任务"><el-option v-for="task in tasks" :key="task.id" :label="task.title" :value="task.id" /></el-select></el-form-item>
          <el-form-item label="来源用例"><el-select v-model="form.test_case_id" clearable filterable placeholder="请选择用例"><el-option v-for="item in testCases" :key="item.id" :label="item.title" :value="item.id" /></el-select></el-form-item>
          <el-form-item label="来源测试单"><el-select v-model="form.test_run_id" clearable filterable placeholder="请选择测试单"><el-option v-for="run in testRuns" :key="run.id" :label="run.name" :value="run.id" /></el-select></el-form-item>
          <el-form-item label="所属迭代"><el-select v-model="form.iteration_id" clearable filterable placeholder="请选择迭代"><el-option v-for="iteration in iterations" :key="iteration.id" :label="iteration.name" :value="iteration.id" /></el-select></el-form-item>
          <el-form-item label="负责人"><el-select v-model="form.owner_id" clearable filterable placeholder="请选择负责人"><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="提出人"><el-select v-model="form.reporter_id" clearable filterable placeholder="请选择提出人"><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="严重程度"><el-select v-model="form.severity"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item>
          <el-form-item label="优先级"><el-select v-model="form.priority"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item>
        </div>
        <el-form-item label="复现步骤"><RichTextPasteEditor v-model="form.reproduce_steps" /></el-form-item>
        <el-form-item label="期望结果"><el-input v-model="form.expected_result" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="实际结果"><el-input v-model="form.actual_result" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitBug">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="actionDialogVisible" :title="bugActionTitle" width="480px">
      <el-form label-position="top">
        <el-form-item v-if="actionType === 'resolve'" label="解决方案" required>
          <el-select v-model="actionForm.resolution">
            <el-option v-for="option in bugResolutionOptions" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="actionType === 'start_fixing'" label="解决迭代">
          <el-select v-model="actionForm.iteration_id" clearable filterable placeholder="请选择解决迭代">
            <el-option v-for="iteration in iterations" :key="iteration.id" :label="iteration.name" :value="iteration.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="actionType === 'suspend'" label="原因">
          <el-input v-model="actionForm.reason" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="actionForm.remark" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="actionDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitBugAction">确认</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { activateBug, closeBug, createBug, deleteBug, fetchBugs, resolveBug, startFixingBug, suspendBug, updateBug } from '../api/bugs'
import { fetchProjects } from '../api/projects'
import { fetchRequirements } from '../api/requirements'
import { fetchTasks } from '../api/tasks'
import { fetchTestCases } from '../api/testCases'
import { fetchTestRuns } from '../api/testRuns'
import { fetchUsers } from '../api/users'
import { fetchIterations } from '../api/iterations'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import RichTextPasteEditor from '../components/RichTextPasteEditor.vue'
import { labelById, userLabel } from '../utils/referenceLabels'
import { usePagination } from '../utils/usePagination'

const loading = ref(false), saving = ref(false), dialogVisible = ref(false), editingId = ref(null)
const actionDialogVisible = ref(false)
const actionType = ref('')
const actingBug = ref(null)
const bugs = ref([]), projects = ref([]), requirements = ref([]), tasks = ref([]), testCases = ref([]), testRuns = ref([]), users = ref([]), iterations = ref([])
const {
  page: bugPage,
  pageSize: bugPageSize,
  pageSizes: bugPageSizes,
  total: bugTotal,
  pagedItems: pagedBugs
} = usePagination(bugs)
const priorityLevelOptions = [
  { label: '① 最高', value: '1' },
  { label: '② 高', value: '2' },
  { label: '③ 中', value: '3' },
  { label: '④ 低', value: '4' },
  { label: '⑤ 最低', value: '5' }
]
const bugStatusOptions = [
  { label: '待确认', value: 'open' },
  { label: '修复中', value: 'fixing' },
  { label: '已解决', value: 'resolved' },
  { label: '待验证', value: 'verifying' },
  { label: '已关闭', value: 'closed' },
  { label: '重新打开', value: 'reopened' },
  { label: '已挂起', value: 'suspended' }
]
const bugResolutionOptions = ['设计如此', '重复Bug', '外部原因', '已解决', '无法重现', '延期处理', '不予解决']
const form = reactive({ project_id: null, iteration_id: null, requirement_id: null, task_id: null, test_case_id: null, test_run_id: null, title: '', severity: '3', priority: '3', owner_id: null, reporter_id: null, reproduce_steps: '', expected_result: '', actual_result: '' })
const actionForm = reactive({ resolution: '', verify_result: '', iteration_id: null, reason: '', remark: '' })
const bugActionTitle = computed(() => ({
  start_fixing: '确认 Bug',
  resolve: '解决 Bug',
  activate: '激活 Bug',
  suspend: '挂起 Bug',
  close: '关闭 Bug'
}[actionType.value] || 'Bug 操作'))

function optionLabel(options, value) { return options.find((option) => option.value === value)?.label || value || '-' }
function bugStatusLabel(value) { return optionLabel(bugStatusOptions, value) }
function resetForm() { Object.assign(form, { project_id: null, iteration_id: null, requirement_id: null, task_id: null, test_case_id: null, test_run_id: null, title: '', severity: '3', priority: '3', owner_id: null, reporter_id: null, reproduce_steps: '', expected_result: '', actual_result: '' }) }
function openCreate() { editingId.value = null; resetForm(); dialogVisible.value = true }
function openEdit(row) { editingId.value = row.id; Object.assign(form, { ...row, reproduce_steps: row.reproduce_steps || '', expected_result: row.expected_result || '', actual_result: row.actual_result || '' }); dialogVisible.value = true }
function apiErrorMessage(error, fallback) { return error?.response?.data?.detail || fallback }
function showActionError(error, fallback) { ElMessageBox.alert(apiErrorMessage(error, fallback), '提示', { type: 'warning' }) }
function openBugAction(row, type) {
  actingBug.value = row
  actionType.value = type
  Object.assign(actionForm, {
    resolution: type === 'resolve' ? '已解决' : '',
    verify_result: type === 'close' ? 'passed' : type === 'activate' ? 'failed' : '',
    iteration_id: type === 'start_fixing' ? row.iteration_id || null : null,
    reason: '',
    remark: ''
  })
  actionDialogVisible.value = true
}

async function loadData() {
  loading.value = true
  try {
    const [bugRes, projectRes, reqRes, taskRes, caseRes, runRes, userRes, iterationRes] = await Promise.all([fetchBugs(), fetchProjects(), fetchRequirements(), fetchTasks(), fetchTestCases(), fetchTestRuns(), fetchUsers(), fetchIterations()])
    bugs.value = bugRes.data; projects.value = projectRes.data; requirements.value = reqRes.data; tasks.value = taskRes.data; testCases.value = caseRes.data; testRuns.value = runRes.data; users.value = userRes.data; iterations.value = iterationRes.data
  } catch { ElMessage.error('Bug 列表加载失败') } finally { loading.value = false }
}
async function submitBug() {
  if (!form.project_id || !form.title.trim()) return ElMessage.warning('请选择项目并填写 Bug 标题')
  saving.value = true
  try {
    const payload = { ...form, iteration_id: form.iteration_id || null, requirement_id: form.requirement_id || null, task_id: form.task_id || null, test_case_id: form.test_case_id || null, test_run_id: form.test_run_id || null, owner_id: form.owner_id || null, reporter_id: form.reporter_id || null }
    delete payload.status
    if (editingId.value) await updateBug(editingId.value, payload); else await createBug(payload)
    dialogVisible.value = false; await loadData()
  } finally { saving.value = false }
}
async function removeBug(id) { await deleteBug(id); await loadData() }
async function submitBugAction() {
  if (actionType.value === 'resolve' && !actionForm.resolution) return ElMessage.warning('请选择解决方案')
  saving.value = true
  try {
    const actions = {
      start_fixing: startFixingBug,
      resolve: resolveBug,
      activate: activateBug,
      suspend: suspendBug,
      close: closeBug
    }
    const payload = ['activate', 'close'].includes(actionType.value) ? { remark: actionForm.remark } : { ...actionForm }
    await actions[actionType.value](actingBug.value.id, payload)
    actionDialogVisible.value = false
    await loadData()
    ElMessage.success('Bug 状态已更新')
  } catch (error) {
    showActionError(error, 'Bug 状态更新失败')
  } finally {
    saving.value = false
  }
}
onMounted(loadData)
</script>
