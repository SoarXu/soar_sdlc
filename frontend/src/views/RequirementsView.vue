<template>
  <section>
    <div class="page-head">
      <div>
        <h1>需求</h1>
        <p>维护需求并生成任务，关联项目、迭代和人员均以名称展示。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增需求</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="requirements" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="需求标题" min-width="220" />
        <el-table-column label="项目" width="180"><template #default="{ row }">{{ labelById(projects, row.project_id) }}</template></el-table-column>
        <el-table-column label="迭代" width="160"><template #default="{ row }">{{ labelById(iterations, row.iteration_id) }}</template></el-table-column>
        <el-table-column label="负责人" width="150"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column prop="priority" label="优先级" width="100" />
        <el-table-column prop="review_status" label="评审状态" width="120" />
        <el-table-column prop="status" label="状态" width="100" />
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
          <el-form-item label="项目" required>
            <el-select v-model="form.project_id" filterable placeholder="请选择项目">
              <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="迭代">
            <el-select v-model="form.iteration_id" clearable filterable placeholder="请选择迭代">
              <el-option v-for="iteration in iterations" :key="iteration.id" :label="iteration.name" :value="iteration.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="负责人">
            <el-select v-model="form.owner_id" clearable filterable placeholder="请选择负责人">
              <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="提出人">
            <el-select v-model="form.proposer_id" clearable filterable placeholder="请选择提出人">
              <el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" />
            </el-select>
          </el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="类型"><el-input v-model="form.requirement_type" /></el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="form.priority">
              <el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="form.status">
              <el-option label="草稿" value="draft" /><el-option label="激活" value="active" /><el-option label="完成" value="done" /><el-option label="关闭" value="closed" />
            </el-select>
          </el-form-item>
          <el-form-item label="评审状态">
            <el-select v-model="form.review_status">
              <el-option label="无需评审" value="not_required" /><el-option label="待评审" value="pending" /><el-option label="已通过" value="approved" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="需求描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="验收标准"><el-input v-model="form.acceptance_criteria" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRequirement">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="generateVisible" title="从需求生成任务" width="480px">
      <el-form label-position="top">
        <el-form-item label="任务标题" required><el-input v-model="generateForm.title" /></el-form-item>
        <el-form-item label="任务类型"><el-input v-model="generateForm.task_type" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="generateForm.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="generateVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitGenerateTask">生成</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { fetchIterations } from '../api/iterations'
import { fetchProjects } from '../api/projects'
import { createRequirement, deleteRequirement, fetchRequirements, generateTask, updateRequirement } from '../api/requirements'
import { fetchUsers } from '../api/users'
import { labelById, userLabel } from '../utils/referenceLabels'

const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const generateVisible = ref(false)
const editingId = ref(null)
const generatingRequirementId = ref(null)
const requirements = ref([])
const projects = ref([])
const iterations = ref([])
const users = ref([])
const form = reactive({ project_id: null, iteration_id: null, title: '', requirement_type: '', priority: 'medium', owner_id: null, proposer_id: null, status: 'draft', review_status: 'not_required', description: '', acceptance_criteria: '', source_reviewed: false })
const generateForm = reactive({ title: '', task_type: '', description: '' })

function resetForm() { Object.assign(form, { project_id: null, iteration_id: null, title: '', requirement_type: '', priority: 'medium', owner_id: null, proposer_id: null, status: 'draft', review_status: 'not_required', description: '', acceptance_criteria: '', source_reviewed: false }) }
function openCreate() { editingId.value = null; resetForm(); dialogVisible.value = true }
function openEdit(row) { editingId.value = row.id; Object.assign(form, { ...row, requirement_type: row.requirement_type || '', description: row.description || '', acceptance_criteria: row.acceptance_criteria || '' }); dialogVisible.value = true }
function openGenerate(row) { generatingRequirementId.value = row.id; generateForm.title = row.title; generateForm.task_type = 'development'; generateForm.description = ''; generateVisible.value = true }

async function loadData() {
  loading.value = true
  try {
    const [reqRes, projectRes, iterationRes, userRes] = await Promise.all([fetchRequirements(), fetchProjects(), fetchIterations(), fetchUsers()])
    requirements.value = reqRes.data; projects.value = projectRes.data; iterations.value = iterationRes.data; users.value = userRes.data
  } catch { ElMessage.error('需求列表加载失败') } finally { loading.value = false }
}

async function submitRequirement() {
  if (!form.project_id || !form.title.trim()) return ElMessage.warning('请选择项目并填写需求标题')
  saving.value = true
  try {
    const payload = { ...form, iteration_id: form.iteration_id || null, owner_id: form.owner_id || null, proposer_id: form.proposer_id || null }
    if (editingId.value) await updateRequirement(editingId.value, payload); else await createRequirement(payload)
    dialogVisible.value = false; await loadData()
  } finally { saving.value = false }
}
async function submitGenerateTask() { if (!generateForm.title.trim()) return ElMessage.warning('请填写任务标题'); saving.value = true; try { await generateTask(generatingRequirementId.value, { ...generateForm }); generateVisible.value = false; ElMessage.success('任务已生成') } finally { saving.value = false } }
async function removeRequirement(id) { await deleteRequirement(id); await loadData() }
onMounted(loadData)
</script>
