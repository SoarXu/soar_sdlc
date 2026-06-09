<template>
  <section>
    <div class="page-head">
      <div>
        <h1>项目</h1>
        <p>维护单个项目、项目集归属、负责人、周期和状态，数据通过后端接口落库。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增项目</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="projects" stripe>
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="name" label="项目名称" min-width="180" />
        <el-table-column prop="program_id" label="项目集 ID" width="120" />
        <el-table-column prop="owner_id" label="负责人 ID" width="120" />
        <el-table-column prop="start_date" label="开始日期" width="130" />
        <el-table-column prop="end_date" label="结束日期" width="130" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column prop="update_time" label="更新时间" width="190" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该项目？" @confirm="removeProject(row.id)">
              <template #reference>
                <el-button link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑项目' : '新增项目'" width="560px">
      <el-form label-position="top">
        <el-form-item label="项目名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="项目集 ID">
            <el-input-number v-model="form.program_id" :min="1" controls-position="right" />
          </el-form-item>
          <el-form-item label="负责人 ID">
            <el-input-number v-model="form.owner_id" :min="1" controls-position="right" />
          </el-form-item>
          <el-form-item label="开始日期">
            <el-date-picker v-model="form.start_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
          <el-form-item label="结束日期">
            <el-date-picker v-model="form.end_date" value-format="YYYY-MM-DD" type="date" />
          </el-form-item>
        </div>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option label="启用" value="active" />
            <el-option label="关闭" value="closed" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" type="textarea" :rows="3" />
        </el-form-item>
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

import { createProject, deleteProject, fetchProjects, updateProject } from '../api/projects'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const projects = ref([])
const form = reactive({
  program_id: null,
  name: '',
  owner_id: null,
  start_date: null,
  end_date: null,
  status: 'active',
  description: ''
})

function resetForm() {
  form.program_id = null
  form.name = ''
  form.owner_id = null
  form.start_date = null
  form.end_date = null
  form.status = 'active'
  form.description = ''
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  form.program_id = row.program_id
  form.name = row.name
  form.owner_id = row.owner_id
  form.start_date = row.start_date
  form.end_date = row.end_date
  form.status = row.status
  form.description = row.description || ''
  dialogVisible.value = true
}

async function loadProjects() {
  loading.value = true
  try {
    const { data } = await fetchProjects()
    projects.value = data
  } catch (error) {
    ElMessage.error('项目列表加载失败，请确认后端服务已启动')
  } finally {
    loading.value = false
  }
}

async function submitProject() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写项目名称')
    return
  }
  saving.value = true
  try {
    const payload = {
      ...form,
      program_id: form.program_id || null,
      owner_id: form.owner_id || null
    }
    if (editingId.value) {
      await updateProject(editingId.value, payload)
    } else {
      await createProject(payload)
    }
    dialogVisible.value = false
    await loadProjects()
  } finally {
    saving.value = false
  }
}

async function removeProject(id) {
  await deleteProject(id)
  await loadProjects()
}

onMounted(loadProjects)
</script>
