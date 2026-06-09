<template>
  <section>
    <div class="page-head">
      <div>
        <h1>迭代</h1>
        <p>维护迭代计划、周期、负责人和目标，数据通过后端接口落库。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增迭代</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="iterations" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="name" label="迭代名称" min-width="180" />
        <el-table-column prop="project_id" label="项目 ID" width="110" />
        <el-table-column prop="owner_id" label="负责人 ID" width="120" />
        <el-table-column prop="start_date" label="开始日期" width="130" />
        <el-table-column prop="end_date" label="结束日期" width="130" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该迭代？" @confirm="removeIteration(row.id)">
              <template #reference><el-button link type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑迭代' : '新增迭代'" width="560px">
      <el-form label-position="top">
        <el-form-item label="迭代名称" required><el-input v-model="form.name" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目 ID" required><el-input-number v-model="form.project_id" :min="1" /></el-form-item>
          <el-form-item label="负责人 ID"><el-input-number v-model="form.owner_id" :min="1" /></el-form-item>
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
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { createIteration, deleteIteration, fetchIterations, updateIteration } from '../api/iterations'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const iterations = ref([])
const form = reactive({ project_id: null, name: '', owner_id: null, start_date: null, end_date: null, status: 'planning', goal: '' })

function resetForm() {
  Object.assign(form, { project_id: null, name: '', owner_id: null, start_date: null, end_date: null, status: 'planning', goal: '' })
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    project_id: row.project_id,
    name: row.name,
    owner_id: row.owner_id,
    start_date: row.start_date,
    end_date: row.end_date,
    status: row.status,
    goal: row.goal || ''
  })
  dialogVisible.value = true
}

async function loadIterations() {
  loading.value = true
  try {
    const { data } = await fetchIterations()
    iterations.value = data
  } catch {
    ElMessage.error('迭代列表加载失败')
  } finally {
    loading.value = false
  }
}

async function submitIteration() {
  if (!form.project_id || !form.name.trim()) {
    ElMessage.warning('请填写项目 ID 和迭代名称')
    return
  }
  saving.value = true
  try {
    const payload = { ...form, owner_id: form.owner_id || null }
    if (editingId.value) await updateIteration(editingId.value, payload)
    else await createIteration(payload)
    dialogVisible.value = false
    await loadIterations()
  } finally {
    saving.value = false
  }
}

async function removeIteration(id) {
  await deleteIteration(id)
  await loadIterations()
}

onMounted(loadIterations)
</script>
