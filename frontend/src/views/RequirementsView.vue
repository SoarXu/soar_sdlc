<template>
  <section>
    <div class="page-head">
      <div>
        <h1>需求</h1>
        <p>维护需求并可按 PRD 默认规则直接生成任务，所有操作通过后端接口落库。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增需求</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="requirements" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="需求标题" min-width="220" />
        <el-table-column prop="project_id" label="项目 ID" width="110" />
        <el-table-column prop="iteration_id" label="迭代 ID" width="110" />
        <el-table-column prop="priority" label="优先级" width="100" />
        <el-table-column prop="owner_id" label="负责人 ID" width="120" />
        <el-table-column prop="review_status" label="评审状态" width="130" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column label="操作" width="230" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
            <el-button link type="success" @click="openGenerate(row)">生成任务</el-button>
            <el-popconfirm title="确认删除该需求？" @confirm="removeRequirement(row.id)">
              <template #reference><el-button link type="danger">删除</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑需求' : '新增需求'" width="640px">
      <el-form label-position="top">
        <el-form-item label="需求标题" required><el-input v-model="form.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目 ID" required><el-input-number v-model="form.project_id" :min="1" /></el-form-item>
          <el-form-item label="迭代 ID"><el-input-number v-model="form.iteration_id" :min="1" /></el-form-item>
          <el-form-item label="负责人 ID"><el-input-number v-model="form.owner_id" :min="1" /></el-form-item>
          <el-form-item label="提出人 ID"><el-input-number v-model="form.proposer_id" :min="1" /></el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="类型"><el-input v-model="form.requirement_type" /></el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="form.priority">
              <el-option label="高" value="high" />
              <el-option label="中" value="medium" />
              <el-option label="低" value="low" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="form.status">
              <el-option label="草稿" value="draft" />
              <el-option label="激活" value="active" />
              <el-option label="完成" value="done" />
              <el-option label="关闭" value="closed" />
            </el-select>
          </el-form-item>
          <el-form-item label="评审状态">
            <el-select v-model="form.review_status">
              <el-option label="无需评审" value="not_required" />
              <el-option label="待评审" value="pending" />
              <el-option label="已通过" value="approved" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="需求描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="验收标准"><el-input v-model="form.acceptance_criteria" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitRequirement">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="generateVisible" title="从需求生成任务" width="480px">
      <el-form label-position="top">
        <el-form-item label="任务标题" required><el-input v-model="generateForm.title" /></el-form-item>
        <el-form-item label="任务类型"><el-input v-model="generateForm.task_type" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="generateForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitGenerateTask">生成</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { createRequirement, deleteRequirement, fetchRequirements, generateTask, updateRequirement } from '../api/requirements'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const generateVisible = ref(false)
const editingId = ref(null)
const generatingRequirementId = ref(null)
const requirements = ref([])
const form = reactive({
  project_id: null,
  iteration_id: null,
  title: '',
  requirement_type: '',
  priority: 'medium',
  owner_id: null,
  proposer_id: null,
  status: 'draft',
  review_status: 'not_required',
  description: '',
  acceptance_criteria: '',
  source_reviewed: false
})
const generateForm = reactive({ title: '', task_type: '', description: '' })

function resetForm() {
  Object.assign(form, {
    project_id: null,
    iteration_id: null,
    title: '',
    requirement_type: '',
    priority: 'medium',
    owner_id: null,
    proposer_id: null,
    status: 'draft',
    review_status: 'not_required',
    description: '',
    acceptance_criteria: '',
    source_reviewed: false
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
    project_id: row.project_id,
    iteration_id: row.iteration_id,
    title: row.title,
    requirement_type: row.requirement_type || '',
    priority: row.priority,
    owner_id: row.owner_id,
    proposer_id: row.proposer_id,
    status: row.status,
    review_status: row.review_status,
    description: row.description || '',
    acceptance_criteria: row.acceptance_criteria || '',
    source_reviewed: row.source_reviewed
  })
  dialogVisible.value = true
}

function openGenerate(row) {
  generatingRequirementId.value = row.id
  generateForm.title = row.title
  generateForm.task_type = 'development'
  generateForm.description = ''
  generateVisible.value = true
}

async function loadRequirements() {
  loading.value = true
  try {
    const { data } = await fetchRequirements()
    requirements.value = data
  } catch {
    ElMessage.error('需求列表加载失败')
  } finally {
    loading.value = false
  }
}

async function submitRequirement() {
  if (!form.project_id || !form.title.trim()) {
    ElMessage.warning('请填写项目 ID 和需求标题')
    return
  }
  saving.value = true
  try {
    const payload = { ...form, iteration_id: form.iteration_id || null, owner_id: form.owner_id || null, proposer_id: form.proposer_id || null }
    if (editingId.value) await updateRequirement(editingId.value, payload)
    else await createRequirement(payload)
    dialogVisible.value = false
    await loadRequirements()
  } finally {
    saving.value = false
  }
}

async function submitGenerateTask() {
  if (!generateForm.title.trim()) {
    ElMessage.warning('请填写任务标题')
    return
  }
  saving.value = true
  try {
    await generateTask(generatingRequirementId.value, { ...generateForm })
    generateVisible.value = false
    ElMessage.success('任务已生成')
  } finally {
    saving.value = false
  }
}

async function removeRequirement(id) {
  await deleteRequirement(id)
  await loadRequirements()
}

onMounted(loadRequirements)
</script>
