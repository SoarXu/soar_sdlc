<template>
  <section class="page exception-rules-page">
    <div class="page-head">
      <div>
        <h1>异常规则</h1>
        <p>配置工作台异常识别阈值与适用范围。</p>
      </div>
      <div class="page-actions">
        <el-button @click="router.push('/admin')">返回后台管理</el-button>
        <el-button type="primary" @click="openCreate">新增覆盖规则</el-button>
      </div>
    </div>

    <el-table v-loading="loading" :data="rules" border stripe>
      <el-table-column prop="label" label="异常" min-width="180" />
      <el-table-column prop="exception_key" label="规则键" min-width="210" />
      <el-table-column label="项目" min-width="160">
        <template #default="{ row }">
          <el-select v-model="row.project_id" clearable placeholder="全部项目">
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="对象" width="145">
        <template #default="{ row }">
          <el-select v-model="row.object_type">
            <el-option v-for="option in objectTypeOptions" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="优先级" width="130">
        <template #default="{ row }">
          <el-select v-model="row.priority" clearable placeholder="全部">
            <el-option v-for="value in ['1', '2', '3', '4', '5']" :key="value" :label="value" :value="value" />
          </el-select>
        </template>
      </el-table-column>
      <el-table-column label="状态" min-width="150">
        <template #default="{ row }"><el-input v-model="row.status" clearable placeholder="全部状态" /></template>
      </el-table-column>
      <el-table-column label="小时阈值" width="130">
        <template #default="{ row }"><el-input-number v-model="row.threshold_hours" :min="0" controls-position="right" /></template>
      </el-table-column>
      <el-table-column label="次数阈值" width="130">
        <template #default="{ row }"><el-input-number v-model="row.threshold_count" :min="0" controls-position="right" /></template>
      </el-table-column>
      <el-table-column label="启用" width="80" align="center">
        <template #default="{ row }"><el-switch v-model="row.enabled" /></template>
      </el-table-column>
      <el-table-column label="操作" width="130" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :loading="savingId === row.id" @click="saveRow(row)">保存</el-button>
          <el-popconfirm title="确认删除该覆盖规则？" @confirm="removeRow(row)">
            <template #reference><el-button link type="danger">删除</el-button></template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="createVisible" title="新增异常覆盖规则" width="620px">
      <el-form label-position="top">
        <el-form-item label="异常类型"><el-select v-model="form.exception_key"><el-option v-for="option in exceptionOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
        <el-form-item label="显示名称"><el-input v-model="form.label" /></el-form-item>
        <div class="exception-rule-form-grid">
          <el-form-item label="项目"><el-select v-model="form.project_id" clearable placeholder="全部项目"><el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" /></el-select></el-form-item>
          <el-form-item label="对象"><el-select v-model="form.object_type"><el-option v-for="option in objectTypeOptions" :key="option.value" :label="option.label" :value="option.value" /></el-select></el-form-item>
          <el-form-item label="优先级"><el-select v-model="form.priority" clearable placeholder="全部"><el-option v-for="value in ['1', '2', '3', '4', '5']" :key="value" :label="value" :value="value" /></el-select></el-form-item>
          <el-form-item label="状态"><el-input v-model="form.status" clearable placeholder="全部状态" /></el-form-item>
          <el-form-item label="小时阈值"><el-input-number v-model="form.threshold_hours" :min="0" controls-position="right" /></el-form-item>
          <el-form-item label="次数阈值"><el-input-number v-model="form.threshold_count" :min="0" controls-position="right" /></el-form-item>
        </div>
      </el-form>
      <template #footer><el-button @click="createVisible = false">取消</el-button><el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { createExceptionRule, deleteExceptionRule, fetchExceptionRules, updateExceptionRule } from '../api/exceptionRules'
import { fetchProjects } from '../api/projects'

const router = useRouter()
const loading = ref(false)
const creating = ref(false)
const savingId = ref(null)
const createVisible = ref(false)
const rules = ref([])
const projects = ref([])

const objectTypeOptions = [
  { label: '全部对象', value: '*' },
  { label: '需求', value: 'requirement' },
  { label: '任务', value: 'task' },
  { label: 'Bug', value: 'bug' }
]
const exceptionOptions = [
  ['unassigned_timeout', '未分派超时'],
  ['pending_timeout', '待处理超时'],
  ['fixing_timeout', '修复/处理超时'],
  ['pending_verification_timeout', '待验证超时'],
  ['verified_not_closed', '已验证未关闭'],
  ['verification_failed', '验证失败'],
  ['repeated_activation', '重复激活'],
  ['high_priority_unprocessed', '高优先级未处理'],
  ['completed_requirement_active_bug', '已完成需求存在活动 Bug']
].map(([value, label]) => ({ value, label }))
const form = reactive(defaultForm())

function defaultForm() {
  return { exception_key: 'unassigned_timeout', label: '未分派超时', object_type: '*', project_id: null, priority: null, status: null, threshold_hours: 24, threshold_count: null, enabled: true, sort_order: 100 }
}

watch(() => form.exception_key, (value) => {
  form.label = exceptionOptions.find((item) => item.value === value)?.label || form.label
})

async function loadData() {
  loading.value = true
  try {
    const [ruleResponse, projectResponse] = await Promise.all([fetchExceptionRules(), fetchProjects()])
    rules.value = ruleResponse.data || []
    projects.value = projectResponse.data || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '加载异常规则失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  Object.assign(form, defaultForm())
  createVisible.value = true
}

function editablePayload(rule) {
  return {
    label: rule.label,
    object_type: rule.object_type,
    project_id: rule.project_id || null,
    priority: rule.priority || null,
    status: rule.status || null,
    threshold_hours: rule.threshold_hours,
    threshold_count: rule.threshold_count,
    enabled: rule.enabled,
    sort_order: rule.sort_order
  }
}

async function saveRow(row) {
  savingId.value = row.id
  try {
    await updateExceptionRule(row.id, editablePayload(row))
    ElMessage.success('异常规则已保存')
    await loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    savingId.value = null
  }
}

async function submitCreate() {
  creating.value = true
  try {
    await createExceptionRule({ ...form, project_id: form.project_id || null, priority: form.priority || null, status: form.status || null })
    createVisible.value = false
    ElMessage.success('覆盖规则已创建')
    await loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}

async function removeRow(row) {
  try {
    await deleteExceptionRule(row.id)
    ElMessage.success('异常规则已删除')
    await loadData()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

onMounted(loadData)
</script>

<style scoped>
.exception-rules-page :deep(.el-select),
.exception-rules-page :deep(.el-input-number) {
  width: 100%;
}

.exception-rule-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}
</style>
