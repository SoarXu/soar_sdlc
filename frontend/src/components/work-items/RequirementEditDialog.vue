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
        <el-form-item label="迭代" required>
          <el-select v-model="form.iteration_id" filterable placeholder="请选择迭代">
            <el-option v-for="iteration in requirementSelectableIterations" :key="iteration.id" :label="requirementIterationLabel(iteration)" :value="iteration.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="提出人">
          <el-input v-model="form.proposer" clearable placeholder="请输入提出人" />
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
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchIterations } from '../../api/iterations'
import { fetchProjects } from '../../api/projects'
import { fetchRequirement, updateRequirement } from '../../api/requirements'
import { showActionError } from '../../utils/actionFeedback'
import { requirementIterationLabel, requirementIterationOptions } from '../../utils/requirementIterations'
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
const form = reactive({})
const priorityOptions = ['1', '2', '3', '4', '5']
const requirementTypeOptions = ['功能', '接口', '性能', '安全', '体验', '改进', '其他']
const legacyPriorities = { high: '1', medium: '3', low: '5' }
const selectedProject = computed(() => projects.value.find((project) => project.id === form.project_id) || null)
const requirementSelectableIterations = computed(() => requirementIterationOptions(
  selectedProject.value,
  projects.value,
  iterations.value
))

async function load() {
  if (!props.modelValue || !props.itemId) return
  loading.value = true
  try {
    const [itemResponse, projectResponse, iterationResponse] = await Promise.all([
      fetchRequirement(props.itemId),
      fetchProjects(),
      fetchIterations()
    ])
    projects.value = projectResponse.data || []
    iterations.value = iterationResponse.data || []
    const item = itemResponse.data || {}
    Object.assign(form, {
      project_id: item.project_id || null,
      source_project_id: item.source_project_id || null,
      iteration_id: item.iteration_id || null,
      title: item.title || '',
      requirement_type: item.requirement_type || '',
      priority: legacyPriorities[item.priority] || item.priority || '3',
      proposer: item.proposer || '',
      description: item.description || '',
      acceptance_criteria: item.acceptance_criteria || ''
    })
    await nextTick()
  } catch (error) {
    showActionError(error, '需求加载失败')
    visible.value = false
  } finally {
    loading.value = false
  }
}

watch(() => form.project_id, (projectId) => {
  if (loading.value || !projectId) return
  if (!requirementSelectableIterations.value.some((iteration) => iteration.id === form.iteration_id)) {
    form.iteration_id = null
  }
})

async function save() {
  if (!form.project_id || !form.iteration_id || !form.title?.trim()) {
    ElMessage.warning('请选择项目、迭代并填写需求标题')
    return
  }
  saving.value = true
  try {
    await updateRequirement(props.itemId, {
      ...form,
      iteration_id: form.iteration_id,
      proposer: form.proposer || null
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

watch(() => [props.modelValue, props.itemId], load, { immediate: true })
</script>

<style scoped>
.form-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0 16px;
}
</style>
