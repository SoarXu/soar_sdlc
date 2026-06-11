<template>
  <section class="project-detail-page">
    <div class="project-detail-head">
      <div>
        <el-button link type="primary" @click="$router.push('/iterations')">返回迭代列表</el-button>
        <h1>{{ iteration.name || '迭代详情' }}</h1>
        <p>{{ projectNames }} · {{ userLabel(users, iteration.owner_id) }} · {{ iteration.start_date || '-' }} 至 {{ iteration.end_date || '-' }}</p>
      </div>
      <el-tag size="large">{{ iterationStatusLabel(iteration.status) }}</el-tag>
    </div>

    <div class="project-tabs">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="project-tab-button"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <el-card v-loading="loading" shadow="never" class="project-detail-card">
      <template v-if="activeTab === 'overview'">
        <div class="metrics project-detail-metrics">
          <el-card shadow="never"><span>需求数</span><strong>{{ metrics.requirement_total || 0 }}</strong></el-card>
          <el-card shadow="never"><span>任务数</span><strong>{{ tasks.length }}</strong></el-card>
          <el-card shadow="never"><span>用例数</span><strong>{{ testCases.length }}</strong></el-card>
          <el-card shadow="never"><span>迭代进度</span><strong>{{ percent(metrics.progress_rate) }}</strong></el-card>
          <el-card shadow="never"><span>测试覆盖率</span><strong>{{ percent(metrics.test_coverage_rate) }}</strong></el-card>
        </div>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="迭代名称">{{ iteration.name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="负责人">{{ userLabel(users, iteration.owner_id) }}</el-descriptions-item>
          <el-descriptions-item label="开始日期">{{ iteration.start_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="结束日期">{{ iteration.end_date || '-' }}</el-descriptions-item>
          <el-descriptions-item label="目标" :span="2">{{ iteration.goal || '-' }}</el-descriptions-item>
        </el-descriptions>
      </template>

      <template v-else-if="activeTab === 'requirements'">
        <div class="project-tab-toolbar"><el-button type="primary" @click="openRequirementLink">关联需求</el-button></div>
        <div v-if="!requirements.length" class="project-tab-placeholder">暂无关联需求</div>
        <div v-else class="iteration-tree-list">
          <div v-for="project in projects" :key="project.id" class="iteration-project-block">
            <h3>{{ project.name }}</h3>
            <ProjectRequirementTree :project="project" :requirements="requirements" @remove="removeRequirement" />
          </div>
        </div>
      </template>

      <template v-else-if="activeTab === 'tasks'">
        <div class="project-tab-toolbar"><el-button type="primary" @click="openTaskLink">关联任务</el-button></div>
        <el-table :data="tasks" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="title" label="任务标题" min-width="220" show-overflow-tooltip />
          <el-table-column label="项目" width="180"><template #default="{ row }">{{ labelById(flatProjects, row.project_id) }}</template></el-table-column>
          <el-table-column label="需求" width="220"><template #default="{ row }">{{ labelById(requirements, row.requirement_id, 'title') }}</template></el-table-column>
          <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
          <el-table-column label="状态" width="110"><template #default="{ row }">{{ taskStatusLabel(row.status) }}</template></el-table-column>
          <el-table-column label="操作" width="120" fixed="right">
            <template #default="{ row }">
              <el-button v-if="row.iteration_id === iterationId" link type="danger" @click="removeTask(row.id)">移除</el-button>
              <span v-else class="muted-text">需求带入</span>
            </template>
          </el-table-column>
        </el-table>
      </template>

      <template v-else>
        <el-table :data="testCases" stripe width="100%">
          <el-table-column prop="id" label="ID" width="80" />
          <el-table-column prop="title" label="用例标题" min-width="220" show-overflow-tooltip />
          <el-table-column label="项目" width="180"><template #default="{ row }">{{ labelById(flatProjects, row.project_id) }}</template></el-table-column>
          <el-table-column label="需求" min-width="220"><template #default="{ row }">{{ labelById(requirements, row.requirement_id, 'title') }}</template></el-table-column>
          <el-table-column prop="case_type" label="类型" width="120" />
          <el-table-column prop="test_scope" label="适用范围" width="150" />
        </el-table>
      </template>
    </el-card>

    <el-dialog v-model="requirementDialogVisible" title="关联需求" width="760px">
      <el-table :data="availableRequirements" @selection-change="selectedRequirementIds = $event.map(item => item.id)" max-height="420">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="title" label="需求标题" min-width="240" />
        <el-table-column label="项目" width="180"><template #default="{ row }">{{ labelById(flatProjects, row.project_id) }}</template></el-table-column>
        <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="{ row }">{{ requirementStatusLabel(row.status) }}</template></el-table-column>
      </el-table>
      <template #footer><el-button @click="requirementDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRequirements">关联</el-button></template>
    </el-dialog>

    <el-dialog v-model="taskDialogVisible" title="关联任务" width="760px">
      <el-table :data="availableTasks" @selection-change="selectedTaskIds = $event.map(item => item.id)" max-height="420">
        <el-table-column type="selection" width="50" />
        <el-table-column prop="title" label="任务标题" min-width="240" />
        <el-table-column label="项目" width="180"><template #default="{ row }">{{ labelById(flatProjects, row.project_id) }}</template></el-table-column>
        <el-table-column label="负责人" width="140"><template #default="{ row }">{{ userLabel(users, row.owner_id) }}</template></el-table-column>
        <el-table-column label="状态" width="110"><template #default="{ row }">{{ taskStatusLabel(row.status) }}</template></el-table-column>
      </el-table>
      <template #footer><el-button @click="taskDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitTasks">关联</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, defineComponent, h, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElButton, ElMessage } from 'element-plus'
import {
  fetchAvailableIterationRequirements,
  fetchAvailableIterationTasks,
  fetchIterationDetail,
  linkIterationRequirements,
  linkIterationTasks,
  unlinkIterationRequirement,
  unlinkIterationTask
} from '../api/iterations'
import { fetchUsers } from '../api/users'
import { labelById, userLabel } from '../utils/referenceLabels'

const route = useRoute()
const iterationId = computed(() => Number(route.params.id))
const loading = ref(false)
const saving = ref(false)
const activeTab = ref('overview')
const iteration = ref({})
const projects = ref([])
const requirements = ref([])
const tasks = ref([])
const testCases = ref([])
const metrics = ref({})
const users = ref([])
const availableRequirements = ref([])
const availableTasks = ref([])
const selectedRequirementIds = ref([])
const selectedTaskIds = ref([])
const requirementDialogVisible = ref(false)
const taskDialogVisible = ref(false)
const tabs = [
  { key: 'overview', label: '概览' },
  { key: 'requirements', label: '需求' },
  { key: 'tasks', label: '任务' },
  { key: 'cases', label: '用例' }
]
const iterationStatusOptions = [
  { label: '规划中', value: 'planning' },
  { label: '进行中', value: 'active' },
  { label: '已完成', value: 'finished' },
  { label: '已关闭', value: 'closed' }
]
const requirementStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '激活', value: 'active' },
  { label: '完成', value: 'done' },
  { label: '关闭', value: 'closed' }
]
const taskStatusOptions = [
  { label: '待办', value: 'todo' },
  { label: '进行中', value: 'doing' },
  { label: '完成', value: 'done' },
  { label: '关闭', value: 'closed' }
]
const flatProjects = computed(() => flattenProjects(projects.value))
const projectNames = computed(() => (iteration.value.project_ids || []).map(id => labelById(flatProjects.value, id)).join('、') || '-')

function optionLabel(options, value) { return options.find((option) => option.value === value)?.label || value || '-' }
function iterationStatusLabel(value) { return optionLabel(iterationStatusOptions, value) }
function requirementStatusLabel(value) { return optionLabel(requirementStatusOptions, value) }
function taskStatusLabel(value) { return optionLabel(taskStatusOptions, value) }
function percent(value) { return `${Math.round((value || 0) * 100)}%` }
function flattenProjects(items) { return items.flatMap((item) => [item, ...flattenProjects(item.children || [])]) }

async function loadData() {
  loading.value = true
  try {
    const [detailRes, userRes] = await Promise.all([fetchIterationDetail(iterationId.value), fetchUsers()])
    iteration.value = detailRes.data.iteration
    projects.value = detailRes.data.projects
    requirements.value = detailRes.data.requirements
    tasks.value = detailRes.data.tasks
    testCases.value = detailRes.data.test_cases
    metrics.value = detailRes.data.metrics
    users.value = userRes.data
  } catch {
    ElMessage.error('迭代详情加载失败')
  } finally {
    loading.value = false
  }
}

async function openRequirementLink() {
  selectedRequirementIds.value = []
  availableRequirements.value = (await fetchAvailableIterationRequirements(iterationId.value)).data
  requirementDialogVisible.value = true
}
async function submitRequirements() {
  if (!selectedRequirementIds.value.length) return ElMessage.warning('请选择需求')
  saving.value = true
  try {
    await linkIterationRequirements(iterationId.value, selectedRequirementIds.value)
    requirementDialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}
async function removeRequirement(requirementId) { await unlinkIterationRequirement(iterationId.value, requirementId); await loadData() }

async function openTaskLink() {
  selectedTaskIds.value = []
  availableTasks.value = (await fetchAvailableIterationTasks(iterationId.value)).data
  taskDialogVisible.value = true
}
async function submitTasks() {
  if (!selectedTaskIds.value.length) return ElMessage.warning('请选择任务')
  saving.value = true
  try {
    await linkIterationTasks(iterationId.value, selectedTaskIds.value)
    taskDialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}
async function removeTask(taskId) { await unlinkIterationTask(iterationId.value, taskId); await loadData() }

const ProjectRequirementTree = defineComponent({
  props: {
    project: { type: Object, required: true },
    requirements: { type: Array, required: true }
  },
  emits: ['remove'],
  setup(props, { emit }) {
    const renderNode = (project, depth = 0) => {
      const rows = props.requirements.filter((item) => item.project_id === project.id)
      return h('div', { class: 'iteration-tree-node' }, [
        depth > 0 ? h('h4', { style: { paddingLeft: `${depth * 18}px` } }, project.name) : null,
        rows.map((row) => h('div', { class: 'iteration-requirement-row', style: { paddingLeft: `${depth * 18 + 12}px` } }, [
          h('span', row.title),
          h(ElButton, { link: true, type: 'danger', onClick: () => emit('remove', row.id) }, () => '移除')
        ])),
        (project.children || []).map((child) => renderNode(child, depth + 1))
      ])
    }
    return () => renderNode(props.project)
  }
})

onMounted(loadData)
</script>
