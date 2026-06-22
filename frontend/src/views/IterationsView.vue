<template>
  <section>
    <div class="page-head">
      <div>
        <h1>迭代</h1>
        <p>维护迭代计划、周期、负责人和目标，关联项目和负责人以名称选择。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增迭代</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="pagedIterations" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="迭代名称" min-width="180">
          <template #default="{ row }"><router-link class="table-link" :to="`/iterations/${row.id}`">{{ row.name }}</router-link></template>
        </el-table-column>
        <el-table-column label="项目" min-width="240"><template #default="{ row }">{{ (row.project_ids || []).map(id => labelById(projects, id)).join('、') }}</template></el-table-column>
        <el-table-column label="负责人" width="150"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="130" />
        <el-table-column prop="end_date" label="结束日期" width="130" />
        <el-table-column prop="actual_start_date" label="实际开始" width="130" />
        <el-table-column prop="actual_end_date" label="实际结束" width="130" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">{{ iterationStatusLabel(row.status) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="210" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.status === 'planning'" link type="success" @click="openStart(row)">开始</el-button>
            <el-button v-if="row.status === 'active'" link type="warning" @click="openFinish(row)">结束</el-button>
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该迭代？" @confirm="removeIteration(row.id)">
              <template #reference><el-button link type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <div class="table-pagination">
        <el-pagination
          v-model:current-page="iterationPage"
          v-model:page-size="iterationPageSize"
          :page-sizes="iterationPageSizes"
          :total="iterationTotal"
          layout="total, sizes, prev, pager, next, jumper"
        />
      </div>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑迭代' : '新增迭代'" width="560px">
      <el-form label-position="top">
        <el-form-item label="迭代名称" required><el-input v-model="form.name" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目" required>
            <el-select v-model="form.project_ids" multiple filterable placeholder="请选择项目">
              <el-option v-for="project in projectOptions" :key="project.id" :label="project.label" :value="project.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="负责人">
            <el-select v-model="form.owner_id" clearable filterable placeholder="请选择负责人">
              <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="开始日期"><el-date-picker v-model="form.start_date" value-format="YYYY-MM-DD" type="date" /></el-form-item>
          <el-form-item label="结束日期"><el-date-picker v-model="form.end_date" value-format="YYYY-MM-DD" type="date" /></el-form-item>
        </div>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option label="规划中" value="planning" />
            <el-option label="进行中" value="active" />
            <el-option label="已完成" value="finished" />
            <el-option label="已关闭" value="closed" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标"><el-input v-model="form.goal" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitIteration">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="startDialogVisible" title="开始迭代" width="480px">
      <el-form label-position="top">
        <el-form-item label="实际开始日期" required>
          <el-date-picker v-model="startForm.effective_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" />
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="startForm.remark" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="startDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitStart">确认开始</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="finishDialogVisible" title="结束迭代" width="480px">
      <el-form label-position="top">
        <el-form-item label="实际结束日期" required>
          <el-date-picker v-model="finishForm.effective_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" />
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="finishForm.remark" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="finishDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitFinish">确认结束</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createIteration, deleteIteration, fetchIterations, finishIteration, startIteration, updateIteration } from '../api/iterations'
import { fetchProjects } from '../api/projects'
import { fetchUsers } from '../api/users'
import { labelById, userLabel } from '../utils/referenceLabels'
import { usePagination } from '../utils/usePagination'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const startDialogVisible = ref(false)
const finishDialogVisible = ref(false)
const editingId = ref(null)
const startingId = ref(null)
const finishingId = ref(null)
const iterations = ref([])
const projects = ref([])
const users = ref([])
const {
  page: iterationPage,
  pageSize: iterationPageSize,
  pageSizes: iterationPageSizes,
  total: iterationTotal,
  pagedItems: pagedIterations
} = usePagination(iterations)
const projectOptions = computed(() => {
  const childrenByParent = projects.value.reduce((result, project) => {
    const key = project.parent_id || 0
    if (!result[key]) result[key] = []
    result[key].push(project)
    return result
  }, {})
  Object.values(childrenByParent).forEach(items => items.sort((a, b) => a.id - b.id))
  const result = []
  const walk = (items, depth = 0) => {
    items.forEach(project => {
      result.push({ ...project, label: `${'　'.repeat(depth)}${project.name}` })
      walk(childrenByParent[project.id] || [], depth + 1)
    })
  }
  walk(childrenByParent[0] || [])
  return result
})
const form = reactive({ project_ids: [], name: '', owner_id: null, start_date: null, end_date: null, status: 'planning', goal: '' })
const startForm = reactive({ effective_time: '', remark: '' })
const finishForm = reactive({ effective_time: '', remark: '' })
const iterationStatusOptions = [
  { label: '规划中', value: 'planning' },
  { label: '进行中', value: 'active' },
  { label: '已完成', value: 'finished' },
  { label: '已关闭', value: 'closed' }
]

function iterationStatusLabel(value) {
  return iterationStatusOptions.find((option) => option.value === value)?.label || value || '-'
}
function resetForm() { Object.assign(form, { project_ids: [], name: '', owner_id: null, start_date: null, end_date: null, status: 'planning', goal: '' }) }
function currentDateTimeValue() {
  const date = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}
function openCreate() { editingId.value = null; resetForm(); dialogVisible.value = true }
function openEdit(row) { editingId.value = row.id; Object.assign(form, { ...row, project_ids: row.project_ids || [], goal: row.goal || '' }); dialogVisible.value = true }
function openStart(row) { startingId.value = row.id; Object.assign(startForm, { effective_time: currentDateTimeValue(), remark: '' }); startDialogVisible.value = true }
function openFinish(row) { finishingId.value = row.id; Object.assign(finishForm, { effective_time: currentDateTimeValue(), remark: '' }); finishDialogVisible.value = true }

async function loadData() {
  loading.value = true
  try {
    const [iterationRes, projectRes, userRes] = await Promise.all([fetchIterations(), fetchProjects(), fetchUsers()])
    iterations.value = iterationRes.data
    projects.value = projectRes.data
    users.value = userRes.data
  } catch {
    ElMessage.error('迭代列表加载失败')
  } finally {
    loading.value = false
  }
}

async function submitIteration() {
  if (!form.project_ids.length || !form.name.trim()) return ElMessage.warning('请选择项目并填写迭代名称')
  saving.value = true
  try {
    const payload = { ...form, owner_id: form.owner_id || null }
    if (editingId.value) await updateIteration(editingId.value, payload)
    else await createIteration(payload)
    dialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}

async function removeIteration(id) { await deleteIteration(id); await loadData() }
async function submitStart() {
  if (!startForm.effective_time) return ElMessage.warning('请选择实际开始日期')
  saving.value = true
  try {
    await startIteration(startingId.value, { ...startForm })
    startDialogVisible.value = false
    await loadData()
    ElMessage.success('迭代已开始')
  } finally {
    saving.value = false
  }
}
async function submitFinish() {
  if (!finishForm.effective_time) return ElMessage.warning('请选择实际结束日期')
  saving.value = true
  try {
    await finishIteration(finishingId.value, { ...finishForm })
    finishDialogVisible.value = false
    await loadData()
    ElMessage.success('迭代已结束')
  } finally {
    saving.value = false
  }
}
onMounted(loadData)
</script>
