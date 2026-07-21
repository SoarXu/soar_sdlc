<template>
  <el-dialog v-model="visible" title="编辑需求" width="640px" destroy-on-close>
    <el-form v-loading="loading" label-position="top">
      <el-form-item label="需求标题" required><el-input v-model="form.title" /></el-form-item>
      <div class="form-grid">
        <el-form-item label="项目" required>
          <el-select v-model="form.project_id" filterable placeholder="请选择项目">
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源项目">
          <el-select v-model="form.source_project_id" clearable filterable placeholder="请选择来源项目">
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="迭代">
          <el-select v-model="form.iteration_id" clearable filterable placeholder="请选择迭代">
            <el-option v-for="iteration in iterations" :key="iteration.id" :label="iteration.name" :value="iteration.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="提出人">
          <el-select v-model="form.proposer_id" clearable filterable placeholder="请选择提出人">
            <el-option v-for="user in users" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
          </el-select>
        </el-form-item>
      </div>
      <div class="form-grid">
        <el-form-item label="类型">
          <el-select v-model="form.requirement_type">
            <el-option v-for="option in requirementTypeOptions" :key="option" :label="option" :value="option" />
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority">
            <template #prefix><RequirementPriorityBadge :value="form.priority" /></template>
            <el-option v-for="option in priorityOptions" :key="option" :label="option" :value="option">
              <RequirementPriorityBadge :value="option" />
            </el-option>
          </el-select>
        </el-form-item>
      </div>
      <el-form-item label="需求描述"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
      <el-form-item label="验收标准"><el-input v-model="form.acceptance_criteria" type="textarea" :rows="3" /></el-form-item>
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

import { fetchIterations } from '../../api/iterations'
import { fetchProjects } from '../../api/projects'
import { fetchRequirement, updateRequirement } from '../../api/requirements'
import { fetchUsers } from '../../api/users'
import { showActionError } from '../../utils/actionFeedback'
import RequirementPriorityBadge from '../RequirementPriorityBadge.vue'

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
const iterations = ref([])
const users = ref([])
const form = reactive({})
const priorityOptions = ['1', '2', '3', '4', '5']
const requirementTypeOptions = ['功能', '接口', '性能', '安全', '体验', '改进', '其他']
const legacyPriorities = { high: '1', medium: '3', low: '5' }

async function load() {
  if (!props.modelValue || !props.itemId) return
  loading.value = true
  try {
    const [itemResponse, projectResponse, iterationResponse, userResponse] = await Promise.all([
      fetchRequirement(props.itemId),
      fetchProjects(),
      fetchIterations(),
      fetchUsers()
    ])
    projects.value = projectResponse.data || []
    iterations.value = iterationResponse.data || []
    users.value = userResponse.data || []
    const item = itemResponse.data || {}
    Object.assign(form, {
      project_id: item.project_id || null,
      source_project_id: item.source_project_id || null,
      iteration_id: item.iteration_id || null,
      title: item.title || '',
      requirement_type: item.requirement_type || '',
      priority: legacyPriorities[item.priority] || item.priority || '3',
      proposer_id: item.proposer_id || null,
      description: item.description || '',
      acceptance_criteria: item.acceptance_criteria || ''
    })
  } catch (error) {
    showActionError(error, '需求加载失败')
    visible.value = false
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!form.project_id || !form.title?.trim()) {
    ElMessage.warning('请选择项目并填写需求标题')
    return
  }
  saving.value = true
  try {
    await updateRequirement(props.itemId, {
      ...form,
      iteration_id: form.iteration_id || null,
      proposer_id: form.proposer_id || null
    })
    visible.value = false
    ElMessage.success('保存成功')
    emit('saved')
  } catch (error) {
    showActionError(error, '需求保存失败')
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
