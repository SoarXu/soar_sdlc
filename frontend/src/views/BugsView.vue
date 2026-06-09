<template>
  <section>
    <div class="page-head">
      <div>
        <h1>Bug</h1>
        <p>维护缺陷和关联上下文，项目、需求、任务、用例、测试单和人员均以名称选择。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增 Bug</el-button>
    </div>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="bugs" stripe>
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="title" label="Bug 标题" min-width="220" />
        <el-table-column label="项目" width="170"><template #default="{ row }">{{ labelById(projects, row.project_id) }}</template></el-table-column>
        <el-table-column label="需求" width="180"><template #default="{ row }">{{ labelById(requirements, row.requirement_id, 'title') }}</template></el-table-column>
        <el-table-column label="任务" width="180"><template #default="{ row }">{{ labelById(tasks, row.task_id, 'title') }}</template></el-table-column>
        <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column prop="severity" label="严重程度" width="110" />
        <el-table-column prop="status" label="状态" width="120" />
        <el-table-column label="操作" width="170" fixed="right">
          <template #default="{ row }"><el-button link type="primary" @click="openEdit(row)">编辑</el-button><el-popconfirm title="确认删除该 Bug？" @confirm="removeBug(row.id)"><template #reference><el-button link type="danger">删除</el-button></template></el-popconfirm></template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑 Bug' : '新增 Bug'" width="700px">
      <el-form label-position="top">
        <el-form-item label="Bug 标题" required><el-input v-model="form.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="项目" required><el-select v-model="form.project_id" filterable placeholder="请选择项目"><el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" /></el-select></el-form-item>
          <el-form-item label="需求"><el-select v-model="form.requirement_id" clearable filterable placeholder="请选择需求"><el-option v-for="requirement in requirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item>
          <el-form-item label="任务"><el-select v-model="form.task_id" clearable filterable placeholder="请选择任务"><el-option v-for="task in tasks" :key="task.id" :label="task.title" :value="task.id" /></el-select></el-form-item>
          <el-form-item label="来源用例"><el-select v-model="form.test_case_id" clearable filterable placeholder="请选择用例"><el-option v-for="item in testCases" :key="item.id" :label="item.title" :value="item.id" /></el-select></el-form-item>
          <el-form-item label="来源测试单"><el-select v-model="form.test_run_id" clearable filterable placeholder="请选择测试单"><el-option v-for="run in testRuns" :key="run.id" :label="run.name" :value="run.id" /></el-select></el-form-item>
          <el-form-item label="负责人"><el-select v-model="form.owner_id" clearable filterable placeholder="请选择负责人"><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="提出人"><el-select v-model="form.reporter_id" clearable filterable placeholder="请选择提出人"><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
        </div>
        <div class="form-grid">
          <el-form-item label="严重程度"><el-select v-model="form.severity"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item>
          <el-form-item label="优先级"><el-select v-model="form.priority"><el-option label="高" value="high" /><el-option label="中" value="medium" /><el-option label="低" value="low" /></el-select></el-form-item>
          <el-form-item label="状态"><el-select v-model="form.status"><el-option label="待修复" value="open" /><el-option label="修复中" value="fixing" /><el-option label="待验证" value="verifying" /><el-option label="已关闭" value="closed" /><el-option label="重新打开" value="reopened" /></el-select></el-form-item>
        </div>
        <el-form-item label="复现步骤"><el-input v-model="form.reproduce_steps" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="期望结果"><el-input v-model="form.expected_result" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="实际结果"><el-input v-model="form.actual_result" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="dialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitBug">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createBug, deleteBug, fetchBugs, updateBug } from '../api/bugs'
import { fetchProjects } from '../api/projects'
import { fetchRequirements } from '../api/requirements'
import { fetchTasks } from '../api/tasks'
import { fetchTestCases } from '../api/testCases'
import { fetchTestRuns } from '../api/testRuns'
import { fetchUsers } from '../api/users'
import { labelById, userLabel } from '../utils/referenceLabels'

const loading = ref(false), saving = ref(false), dialogVisible = ref(false), editingId = ref(null)
const bugs = ref([]), projects = ref([]), requirements = ref([]), tasks = ref([]), testCases = ref([]), testRuns = ref([]), users = ref([])
const form = reactive({ project_id: null, requirement_id: null, task_id: null, test_case_id: null, test_run_id: null, title: '', severity: 'medium', priority: 'medium', owner_id: null, reporter_id: null, reproduce_steps: '', expected_result: '', actual_result: '', status: 'open' })

function resetForm() { Object.assign(form, { project_id: null, requirement_id: null, task_id: null, test_case_id: null, test_run_id: null, title: '', severity: 'medium', priority: 'medium', owner_id: null, reporter_id: null, reproduce_steps: '', expected_result: '', actual_result: '', status: 'open' }) }
function openCreate() { editingId.value = null; resetForm(); dialogVisible.value = true }
function openEdit(row) { editingId.value = row.id; Object.assign(form, { ...row, reproduce_steps: row.reproduce_steps || '', expected_result: row.expected_result || '', actual_result: row.actual_result || '' }); dialogVisible.value = true }

async function loadData() {
  loading.value = true
  try {
    const [bugRes, projectRes, reqRes, taskRes, caseRes, runRes, userRes] = await Promise.all([fetchBugs(), fetchProjects(), fetchRequirements(), fetchTasks(), fetchTestCases(), fetchTestRuns(), fetchUsers()])
    bugs.value = bugRes.data; projects.value = projectRes.data; requirements.value = reqRes.data; tasks.value = taskRes.data; testCases.value = caseRes.data; testRuns.value = runRes.data; users.value = userRes.data
  } catch { ElMessage.error('Bug 列表加载失败') } finally { loading.value = false }
}
async function submitBug() {
  if (!form.project_id || !form.title.trim()) return ElMessage.warning('请选择项目并填写 Bug 标题')
  saving.value = true
  try {
    const payload = { ...form, requirement_id: form.requirement_id || null, task_id: form.task_id || null, test_case_id: form.test_case_id || null, test_run_id: form.test_run_id || null, owner_id: form.owner_id || null, reporter_id: form.reporter_id || null }
    if (editingId.value) await updateBug(editingId.value, payload); else await createBug(payload)
    dialogVisible.value = false; await loadData()
  } finally { saving.value = false }
}
async function removeBug(id) { await deleteBug(id); await loadData() }
onMounted(loadData)
</script>
