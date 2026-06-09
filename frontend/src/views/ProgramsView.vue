<template>
  <section>
    <div class="page-head">
      <div>
        <h1>项目集</h1>
        <p>管理跨项目集合、负责人、部门和状态，所有变更通过后端接口写入数据库。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增项目集</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="programs" stripe>
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column prop="name" label="项目集名称" min-width="180" />
        <el-table-column prop="owner_id" label="负责人 ID" width="120" />
        <el-table-column prop="department" label="部门" width="150" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column prop="update_time" label="更新时间" width="190" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该项目集？" @confirm="removeProgram(row.id)">
              <template #reference>
                <el-button link type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑项目集' : '新增项目集'" width="520px">
      <el-form label-position="top">
        <el-form-item label="项目集名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="负责人 ID">
          <el-input-number v-model="form.owner_id" :min="1" controls-position="right" />
        </el-form-item>
        <el-form-item label="部门">
          <el-input v-model="form.department" />
        </el-form-item>
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
        <el-button type="primary" :loading="saving" @click="submitProgram">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { createProgram, deleteProgram, fetchPrograms, updateProgram } from '../api/programs'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const programs = ref([])
const form = reactive({
  name: '',
  owner_id: null,
  department: '',
  status: 'active',
  description: ''
})

function resetForm() {
  form.name = ''
  form.owner_id = null
  form.department = ''
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
  form.name = row.name
  form.owner_id = row.owner_id
  form.department = row.department || ''
  form.status = row.status
  form.description = row.description || ''
  dialogVisible.value = true
}

async function loadPrograms() {
  loading.value = true
  try {
    const { data } = await fetchPrograms()
    programs.value = data
  } catch (error) {
    ElMessage.error('项目集加载失败，请确认后端服务已启动')
  } finally {
    loading.value = false
  }
}

async function submitProgram() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写项目集名称')
    return
  }
  saving.value = true
  try {
    const payload = { ...form, owner_id: form.owner_id || null }
    if (editingId.value) {
      await updateProgram(editingId.value, payload)
    } else {
      await createProgram(payload)
    }
    dialogVisible.value = false
    await loadPrograms()
  } finally {
    saving.value = false
  }
}

async function removeProgram(id) {
  await deleteProgram(id)
  await loadPrograms()
}

onMounted(loadPrograms)
</script>
