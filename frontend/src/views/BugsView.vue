<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Bug</h1>
        <p>维护缺陷、关联需求/任务/测试上下文和状态流转，所有变更通过后端接口落库。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增 Bug</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="bugs" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="Bug 标题" min-width="220" />
        <el-table-column prop="project_id" label="项目 ID" width="100" />
        <el-table-column prop="requirement_id" label="需求 ID" width="100" />
        <el-table-column prop="task_id" label="任务 ID" width="100" />
        <el-table-column prop="severity" label="严重程度" width="110" />
        <el-table-column prop="priority" label="优先级" width="100" />
        <el-table-column prop="owner_id" label="负责人 ID" width="120" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-popconfirm title="确认删除该 Bug？" @confirm="removeBug(row.id)">
              <template #reference><el-button link type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑 Bug' : '新增 Bug'" width="680px">
      <el-form label-position="top">
        <el-form-item label="Bug 标题" required><el-input v-model="form.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目 ID" required><el-input-number v-model="form.project_id" :min="1" /></el-form-item>
          <el-form-item label="需求 ID"><el-input-number v-model="form.requirement_id" :min="1" /></el-form-item>
          <el-form-item label="任务 ID"><el-input-number v-model="form.task_id" :min="1" /></el-form-item>
          <el-form-item label="用例 ID"><el-input-number v-model="form.test_case_id" :min="1" /></el-form-item>
          <el-form-item label="测试单 ID"><el-input-number v-model="form.test_run_id" :min="1" /></el-form-item>
          <el-form-item label="负责人 ID"><el-input-number v-model="form.owner_id" :min="1" /></el-form-item>
          <el-form-item label="提出人 ID"><el-input-number v-model="form.reporter_id" :min="1" /></el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="严重程度">
            <el-select v-model="form.severity">
              <el-option label="高" value="high" />
              <el-option label="中" value="medium" />
              <el-option label="低" value="low" />
            </el-select>
          </el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="form.priority">
              <el-option label="高" value="high" />
              <el-option label="中" value="medium" />
              <el-option label="低" value="low" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="form.status">
              <el-option label="待修复" value="open" />
              <el-option label="修复中" value="fixing" />
              <el-option label="待验证" value="verifying" />
              <el-option label="已关闭" value="closed" />
              <el-option label="重新打开" value="reopened" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="复现步骤"><el-input v-model="form.reproduce_steps" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="期望结果"><el-input v-model="form.expected_result" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="实际结果"><el-input v-model="form.actual_result" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitBug">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { createBug, deleteBug, fetchBugs, updateBug } from '../api/bugs'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editingId = ref(null)
const bugs = ref([])
const form = reactive({
  project_id: null,
  requirement_id: null,
  task_id: null,
  test_case_id: null,
  test_run_id: null,
  title: '',
  severity: 'medium',
  priority: 'medium',
  owner_id: null,
  reporter_id: null,
  reproduce_steps: '',
  expected_result: '',
  actual_result: '',
  status: 'open'
})

function resetForm() {
  Object.assign(form, {
    project_id: null,
    requirement_id: null,
    task_id: null,
    test_case_id: null,
    test_run_id: null,
    title: '',
    severity: 'medium',
    priority: 'medium',
    owner_id: null,
    reporter_id: null,
    reproduce_steps: '',
    expected_result: '',
    actual_result: '',
    status: 'open'
  })
}

function openCreate() {
  editingId.value = null
  resetForm()
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  Object.assign(form, {
    ...row,
    reproduce_steps: row.reproduce_steps || '',
    expected_result: row.expected_result || '',
    actual_result: row.actual_result || ''
  })
  dialogVisible.value = true
}

async function loadBugs() {
  loading.value = true
  try {
    bugs.value = (await fetchBugs()).data
  } catch {
    ElMessage.error('Bug 列表加载失败')
  } finally {
    loading.value = false
  }
}

async function submitBug() {
  if (!form.project_id || !form.title.trim()) {
    ElMessage.warning('请填写项目 ID 和 Bug 标题')
    return
  }
  saving.value = true
  try {
    const payload = {
      ...form,
      requirement_id: form.requirement_id || null,
      task_id: form.task_id || null,
      test_case_id: form.test_case_id || null,
      test_run_id: form.test_run_id || null,
      owner_id: form.owner_id || null,
      reporter_id: form.reporter_id || null
    }
    if (editingId.value) await updateBug(editingId.value, payload)
    else await createBug(payload)
    dialogVisible.value = false
    await loadBugs()
  } finally {
    saving.value = false
  }
}

async function removeBug(id) {
  await deleteBug(id)
  await loadBugs()
}

onMounted(loadBugs)
</script>
