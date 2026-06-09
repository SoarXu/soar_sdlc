<template>
  <section>
    <div class="page-head">
      <div>
        <h1>任务</h1>
        <p>维护研发执行任务，关联项目、需求和负责人均以名称展示。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增任务</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="pagedTasks" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="任务标题" min-width="220" />
        <el-table-column label="项目" width="180"><template #default="{ row }">{{ labelById(projects, row.project_id) }}</template></el-table-column>
        <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(requirements, row.requirement_id, 'title') }}</template></el-table-column>
        <el-table-column label="负责人" width="150"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column prop="actual_hours" label="实际工时" width="110" />
        <el-table-column prop="due_date" label="截止日期" width="130" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该任务？" @confirm="removeTask(row.id)">
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
            <el-select v-model="form.project_id" filterable placeholder="请选择项目">
              <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="需求">
            <el-select v-model="form.requirement_id" clearable filterable placeholder="请选择需求">
              <el-option v-for="requirement in requirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="负责人">
            <el-select v-model="form.owner_id" clearable filterable placeholder="请选择负责人">
              <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="截止日期"><el-date-picker v-model="form.due_date" value-format="YYYY-MM-DD" type="date" /></el-form-item>
          <el-form-item label="预计工时"><el-input-number v-model="form.estimated_hours" :min="0" :precision="2" /></el-form-item>
          <el-form-item label="实际工时"><el-input-number v-model="form.actual_hours" :min="0" :precision="2" /></el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="类型"><el-input v-model="form.task_type" /></el-form-item>
          <el-form-item label="优先级"><el-select v-model="form.priority"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item>
          <el-form-item label="状态"><el-select v-model="form.status"><el-option label="待办" value="todo" /><el-option label="进行中" value="doing" /><el-option label="完成" value="done" /><el-option label="关闭" value="closed" /></el-select></el-form-item>
        </div>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitTask">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchProjects } from '../api/projects'
import { fetchRequirements } from '../api/requirements'
import { createTask, deleteTask, fetchTasks, updateTask } from '../api/tasks'
import { fetchUsers } from '../api/users'
import { labelById, userLabel } from '../utils/referenceLabels'
import { usePagination } from '../utils/usePagination'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const tasks = ref([])
const projects = ref([])
const requirements = ref([])
const users = ref([])
const {
  page: taskPage,
  pageSize: taskPageSize,
  pageSizes: taskPageSizes,
  total: taskTotal,
  pagedItems: pagedTasks
} = usePagination(tasks)
const form = reactive({ project_id: null, requirement_id: null, title: '', task_type: '', priority: 'medium', owner_id: null, estimated_hours: null, actual_hours: null, due_date: null, status: 'todo', description: '' })

function resetForm() { Object.assign(form, { project_id: null, requirement_id: null, title: '', task_type: '', priority: 'medium', owner_id: null, estimated_hours: null, actual_hours: null, due_date: null, status: 'todo', description: '' }) }
function openCreate() { editingId.value = null; resetForm(); dialogVisible.value = true }
function openEdit(row) { editingId.value = row.id; Object.assign(form, { ...row, task_type: row.task_type || '', description: row.description || '' }); dialogVisible.value = true }

async function loadData() {
  loading.value = true
  try {
    const [taskRes, projectRes, reqRes, userRes] = await Promise.all([fetchTasks(), fetchProjects(), fetchRequirements(), fetchUsers()])
    tasks.value = taskRes.data; projects.value = projectRes.data; requirements.value = reqRes.data; users.value = userRes.data
  } catch { ElMessage.error('任务列表加载失败') } finally { loading.value = false }
}
async function submitTask() {
  if (!form.project_id || !form.title.trim()) return ElMessage.warning('请选择项目并填写任务标题')
  saving.value = true
  try {
    const payload = { ...form, requirement_id: form.requirement_id || null, owner_id: form.owner_id || null }
    if (editingId.value) await updateTask(editingId.value, payload); else await createTask(payload)
    dialogVisible.value = false; await loadData()
  } finally { saving.value = false }
}
async function removeTask(id) { await deleteTask(id); await loadData() }
onMounted(loadData)
</script>
