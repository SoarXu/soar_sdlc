<template>
  <section>
    <div class="page-head">
      <div>
        <h1>项目集</h1>
        <p>管理跨项目集合、负责人、部门和状态，关联负责人以姓名展示。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增项目集</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="programs" stripe>
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="name" label="项目集名称" min-width="180" />
        <el-table-column label="负责人" width="150">
          <template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template>
        </el-table-column>
        <el-table-column prop="department" label="部门" width="150" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column prop="update_time" label="更新时间" width="190" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该项目集？" @confirm="removeProgram(row.id)">
              <template #reference><el-button link type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑项目集' : '新增项目集'" width="520px">
      <el-form label-position="top">
        <el-form-item label="项目集名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="负责人">
          <el-select v-model="form.owner_id" clearable filterable placeholder="请选择负责人">
            <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="部门"><el-input v-model="form.department" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status">
            <el-option label="启用" value="active" />
            <el-option label="关闭" value="closed" />
          </el-select>
        </el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitProgram">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { createProgram, deleteProgram, fetchPrograms, updateProgram } from '../api/programs'
import { fetchUsers } from '../api/users'
import { userLabel } from '../utils/referenceLabels'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const programs = ref([])
const users = ref([])
const form = reactive({ name: '', owner_id: null, department: '', status: 'active', description: '' })

function resetForm() {
  Object.assign(form, { name: '', owner_id: null, department: '', status: 'active', description: '' })
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, { name: row.name, owner_id: row.owner_id, department: row.department || '', status: row.status, description: row.description || '' })
  dialogVisible.value = true
}

async function loadData() {
  loading.value = true
  try {
    const [programRes, userRes] = await Promise.all([fetchPrograms(), fetchUsers()])
    programs.value = programRes.data
    users.value = userRes.data
  } catch {
    ElMessage.error('项目集加载失败')
  } finally {
    loading.value = false
  }
}

async function submitProgram() {
  if (!form.name.trim()) return ElMessage.warning('请填写项目集名称')
  saving.value = true
  try {
    if (editingId.value) await updateProgram(editingId.value, { ...form })
    else await createProgram({ ...form })
    dialogVisible.value = false
    await loadData()
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
