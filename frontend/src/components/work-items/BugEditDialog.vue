<template>
  <el-dialog v-model="visible" title="编辑 Bug" width="700px" destroy-on-close>
    <el-form v-loading="loading" label-position="top">
      <el-form-item label="Bug 标题" required><el-input v-model="form.title" /></el-form-item>
      <div class="form-grid">
        <el-form-item label="项目" required>
          <el-select v-model="form.project_id" filterable placeholder="请选择项目">
            <el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="需求">
          <el-select v-model="form.requirement_id" clearable filterable placeholder="请选择需求">
            <el-option v-for="requirement in requirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="任务">
          <el-select v-model="form.task_id" clearable filterable placeholder="请选择任务">
            <el-option v-for="task in tasks" :key="task.id" :label="task.title" :value="task.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源用例">
          <el-select v-model="form.test_case_id" clearable filterable placeholder="请选择用例">
            <el-option v-for="item in testCases" :key="item.id" :label="item.title" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="来源测试单">
          <el-select v-model="form.test_run_id" clearable filterable placeholder="请选择测试单">
            <el-option v-for="run in testRuns" :key="run.id" :label="run.name" :value="run.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属迭代">
          <el-select v-model="form.iteration_id" clearable filterable placeholder="请选择迭代">
            <el-option v-for="iteration in editableIterationOptions" :key="iteration.id" :label="iteration.name" :value="iteration.id" :disabled="iteration.disabled" />
          </el-select>
        </el-form-item>
        <el-form-item label="提出人">
          <el-select v-model="form.reporter_id" clearable filterable placeholder="请选择提出人">
            <el-option v-for="user in users" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
          </el-select>
        </el-form-item>
      </div>
      <div class="form-grid">
        <el-form-item label="严重程度">
          <el-select v-model="form.severity">
            <el-option v-for="option in priorityOptions" :key="option" :label="option" :value="option"><RequirementPriorityBadge :value="option" /></el-option>
          </el-select>
        </el-form-item>
        <el-form-item label="优先级">
          <el-select v-model="form.priority">
            <el-option v-for="option in priorityOptions" :key="option" :label="option" :value="option"><RequirementPriorityBadge :value="option" /></el-option>
          </el-select>
        </el-form-item>
      </div>
      <el-form-item label="复现步骤"><RichTextPasteEditor v-model="form.reproduce_steps" /></el-form-item>
      <el-form-item label="期望结果"><el-input v-model="form.expected_result" type="textarea" :rows="2" /></el-form-item>
      <el-form-item label="实际结果"><el-input v-model="form.actual_result" type="textarea" :rows="2" /></el-form-item>
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

import { fetchBug, updateBug } from '../../api/bugs'
import { fetchIterations } from '../../api/iterations'
import { fetchProjects } from '../../api/projects'
import { fetchRequirements } from '../../api/requirements'
import { fetchTasks } from '../../api/tasks'
import { fetchTestCases } from '../../api/testCases'
import { fetchTestRuns } from '../../api/testRuns'
import { fetchUsers } from '../../api/users'
import { showActionError } from '../../utils/actionFeedback'
import { bugIterationOptions, includeSelectedIterationOption } from '../../utils/bugIterations'
import RequirementPriorityBadge from '../RequirementPriorityBadge.vue'
import RichTextPasteEditor from '../RichTextPasteEditor.vue'

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
const tasks = ref([])
const testCases = ref([])
const testRuns = ref([])
const users = ref([])
const iterations = ref([])
const form = reactive({})
const priorityOptions = ['1', '2', '3', '4', '5']
const editableIterationOptions = computed(() => includeSelectedIterationOption(
  bugIterationOptions(iterations.value, projects.value, form.project_id),
  iterations.value,
  form.iteration_id
))

async function load() {
  if (!props.modelValue || !props.itemId) return
  loading.value = true
  try {
    const responses = await Promise.all([
      fetchBug(props.itemId),
      fetchProjects(),
      fetchRequirements(),
      fetchTasks(),
      fetchTestCases(),
      fetchTestRuns(),
      fetchUsers(),
      fetchIterations()
    ])
    const [itemResponse, projectResponse, requirementResponse, taskResponse, caseResponse, runResponse, userResponse, iterationResponse] = responses
    projects.value = projectResponse.data || []
    requirements.value = requirementResponse.data || []
    tasks.value = taskResponse.data || []
    testCases.value = caseResponse.data || []
    testRuns.value = runResponse.data || []
    users.value = userResponse.data || []
    iterations.value = iterationResponse.data || []
    const item = itemResponse.data || {}
    Object.assign(form, {
      project_id: item.project_id || null,
      iteration_id: item.iteration_id || null,
      requirement_id: item.requirement_id || null,
      task_id: item.task_id || null,
      test_case_id: item.test_case_id || null,
      test_run_id: item.test_run_id || null,
      title: item.title || '',
      severity: item.severity || '3',
      priority: item.priority || '3',
      reporter_id: item.reporter_id || null,
      reproduce_steps: item.reproduce_steps || '',
      expected_result: item.expected_result || '',
      actual_result: item.actual_result || ''
    })
  } catch (error) {
    showActionError(error, 'Bug 加载失败')
    visible.value = false
  } finally {
    loading.value = false
  }
}

async function save() {
  if (!form.project_id || !form.title?.trim()) {
    ElMessage.warning('请选择项目并填写 Bug 标题')
    return
  }
  saving.value = true
  try {
    await updateBug(props.itemId, {
      ...form,
      iteration_id: form.iteration_id || null,
      requirement_id: form.requirement_id || null,
      task_id: form.task_id || null,
      test_case_id: form.test_case_id || null,
      test_run_id: form.test_run_id || null,
      reporter_id: form.reporter_id || null
    })
    visible.value = false
    ElMessage.success('保存成功')
    emit('saved')
  } catch (error) {
    showActionError(error, 'Bug 保存失败')
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
