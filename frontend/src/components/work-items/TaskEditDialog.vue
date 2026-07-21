<template>
  <el-dialog v-model="visible" title="编辑任务" width="620px" destroy-on-close>
    <el-form v-loading="loading" label-position="top">
      <el-form-item label="任务标题" required><el-input v-model="form.title" /></el-form-item>
      <div class="form-grid">
        <el-form-item label="项目" required>
          <el-select v-model="form.project_id" filterable placeholder="请选择项目" @change="onProjectChange">
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源项目">
          <el-select v-model="form.source_project_id" clearable filterable placeholder="请选择来源项目">
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="需求">
          <el-select v-model="form.requirement_id" clearable filterable placeholder="请选择需求" @change="onRequirementChange">
            <el-option v-for="requirement in availableRequirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="任务分支" required>
          <el-select v-model="form.task_type" :disabled="Boolean(form.requirement_id)">
            <el-option v-for="option in TASK_BRANCH_OPTIONS" :key="option.value" :label="option.label" :value="option.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="截止日期"><el-date-picker v-model="form.due_date" value-format="YYYY-MM-DD" type="date" /></el-form-item>
      </div>
      <el-form-item label="优先级">
        <el-select v-model="form.priority">
          <el-option label="高" value="high" />
          <el-option label="中" value="medium" />
          <el-option label="低" value="low" />
        </el-select>
      </el-form-item>
      <el-form-item label="描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="saving" :disabled="loading" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchProjects } from '../../api/projects'
import { fetchRequirements } from '../../api/requirements'
import { fetchTask, updateTask } from '../../api/tasks'
import { fetchUsers } from '../../api/users'
import { showActionError } from '../../utils/actionFeedback'
import { deriveTaskBranch, TASK_BRANCH_OPTIONS } from '../../utils/taskBranchRules'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  itemId: { type: Number, default: null }
})
const emit = defineEmits(['update:modelValue', 'saved'])

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})
const loading = ref(false)
const saving = ref(false)
const projects = ref([])
const requirements = ref([])
const form = reactive({})
const availableRequirements = computed(() => requirements.value.filter((item) => !form.project_id || item.project_id === form.project_id))

function onProjectChange(projectId) {
  const requirement = requirements.value.find((item) => item.id === form.requirement_id)
  if (requirement && requirement.project_id !== projectId) form.requirement_id = null
  form.task_type = deriveTaskBranch({ requirementId: form.requirement_id, currentType: form.task_type })
}

function onRequirementChange(requirementId) {
  form.task_type = deriveTaskBranch({ requirementId, currentType: requirementId ? null : form.task_type })
}

async function load() {
  if (!props.modelValue || !props.itemId) return
  loading.value = true
  try {
    const [itemResponse, projectResponse, requirementResponse] = await Promise.all([
      fetchTask(props.itemId),
      fetchProjects(),
      fetchRequirements(),
      fetchUsers()
    ])
    projects.value = projectResponse.data || []
    requirements.value = requirementResponse.data || []
    const item = itemResponse.data || {}
    Object.assign(form, {
      project_id: item.project_id || null,
      source_project_id: item.source_project_id || null,
      requirement_id: item.requirement_id || null,
      title: item.title || '',
      task_type: deriveTaskBranch({ requirementId: item.requirement_id, currentType: item.task_type }),
      priority: item.priority || 'medium',
      due_date: item.due_date || null,
      description: item.description || ''
    })
  } catch (error) {
    showActionError(error, '任务加载失败')
    visible.value = false
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!form.project_id || !form.title?.trim()) {
    ElMessage.warning('请选择项目并填写任务标题')
    return
  }
  saving.value = true
  try {
    await updateTask(props.itemId, {
      ...form,
      requirement_id: form.requirement_id || null,
      task_type: deriveTaskBranch({ requirementId: form.requirement_id, currentType: form.task_type })
    })
    visible.value = false
    ElMessage.success('保存成功')
    emit('saved')
  } catch (error) {
    showActionError(error, '任务保存失败')
  } finally {
    saving.value = false
  }
}

watch(() => [props.modelValue, props.itemId], load)
</script>

<style scoped>
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}
</style>
