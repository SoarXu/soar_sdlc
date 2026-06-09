<template>
  <section>
    <div class="page-head">
      <div>
        <h1>项目</h1>
        <p>维护项目归属、负责人、周期和状态，关联对象使用名称展示。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增项目</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="projects" stripe>
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="name" label="项目名称" min-width="180" />
        <el-table-column label="所属项目集" width="180">
          <template #default="{ row }">{{ labelById(programs, row.program_id) }}</template>
        </el-table-column>
        <el-table-column label="负责人" width="150">
          <template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template>
        </el-table-column>
        <el-table-column prop="start_date" label="开始日期" width="130" />
        <el-table-column prop="end_date" label="结束日期" width="130" />
        <el-table-column label="状态" width="110">
          <template #default="{ row }">{{ projectStatusLabel(row.status) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该项目？" @confirm="removeProject(row.id)">
              <template #reference><el-button link type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑项目' : '新增项目'" width="560px">
      <el-form label-position="top">
        <el-form-item label="项目名称" required><el-input v-model="form.name" /></el-form-item>
        <div class="form-grid">
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
          <el-form-item label="开始日期"><el-date-picker v-model="form.start_date" value-format="YYYY-MM-DD" type="date" /></el-form-item>
          <el-form-item label="结束日期"><el-date-picker v-model="form.end_date" value-format="YYYY-MM-DD" type="date" /></el-form-item>
        </div>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option v-for="option in projectStatusOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitProject">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchPrograms } from '../api/programs'
import { createProject, deleteProject, fetchProjects, updateProject } from '../api/projects'
import { fetchUsers } from '../api/users'
import { labelById, userLabel } from '../utils/referenceLabels'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const projects = ref([])
const programs = ref([])
const users = ref([])
const form = reactive({ program_id: null, name: '', owner_id: null, start_date: null, end_date: null, status: 'active', description: '' })
const projectStatusOptions = [
  { label: '规划中', value: 'planning' },
  { label: '进行中', value: 'active' },
  { label: '已暂停', value: 'paused' },
  { label: '已关闭', value: 'closed' }
]

function projectStatusLabel(value) {
  return projectStatusOptions.find((option) => option.value === value)?.label || value || '-'
}

function resetForm() {
  Object.assign(form, { program_id: null, name: '', owner_id: null, start_date: null, end_date: null, status: 'active', description: '' })
}

function openCreate() { editingId.value = null; resetForm(); dialogVisible.value = true }
function openEdit(row) { editingId.value = row.id; Object.assign(form, { ...row, description: row.description || '' }); dialogVisible.value = true }

async function loadData() {
  loading.value = true
  try {
    const [projectRes, programRes, userRes] = await Promise.all([fetchProjects(), fetchPrograms(), fetchUsers()])
    projects.value = projectRes.data
    programs.value = programRes.data
    users.value = userRes.data
  } catch {
    ElMessage.error('项目列表加载失败')
  } finally {
    loading.value = false
  }
}

async function submitProject() {
  if (!form.name.trim()) return ElMessage.warning('请填写项目名称')
  saving.value = true
  try {
    const payload = { ...form, program_id: form.program_id || null, owner_id: form.owner_id || null }
    if (editingId.value) await updateProject(editingId.value, payload)
    else await createProject(payload)
    dialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}

async function removeProject(id) { await deleteProject(id); await loadData() }
onMounted(loadData)
</script>
