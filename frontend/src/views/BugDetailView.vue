<template>
  <section class="requirement-detail-page">
    <div class="detail-titlebar">
      <el-button @click="goBack">返回</el-button>
      <el-tag effect="plain">#{{ bug.id }}</el-tag>
      <h1>{{ bug.title || 'Bug 详情' }}</h1>
      <router-link v-if="bug.project_id" class="detail-link" :to="`/projects/${bug.project_id}?tab=bugs`">进入项目</router-link>
      <el-button v-if="!editing" type="primary" @click="startEdit">编辑</el-button>
      <template v-else>
        <el-button @click="cancelEdit">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveBug">保存</el-button>
      </template>
    </div>

    <el-card v-loading="loading" shadow="never" class="detail-panel">
      <el-form v-if="editing" label-position="top">
        <el-form-item label="Bug 标题" required><el-input v-model="bugForm.title" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="所属项目"><el-select v-model="bugForm.project_id" clearable filterable><el-option v-for="project in projects" :key="project.id" :label="project.name" :value="project.id" /></el-select></el-form-item>
          <el-form-item label="所属迭代"><el-select v-model="bugForm.iteration_id" clearable filterable><el-option v-for="iteration in iterations" :key="iteration.id" :label="iteration.name" :value="iteration.id" /></el-select></el-form-item>
          <el-form-item label="关联需求"><el-select v-model="bugForm.requirement_id" clearable filterable><el-option v-for="requirement in requirements" :key="requirement.id" :label="requirement.title" :value="requirement.id" /></el-select></el-form-item>
          <el-form-item label="关联任务"><el-select v-model="bugForm.task_id" clearable filterable><el-option v-for="task in tasks" :key="task.id" :label="task.title" :value="task.id" /></el-select></el-form-item>
          <el-form-item label="来源用例"><el-select v-model="bugForm.test_case_id" clearable filterable><el-option v-for="item in testCases" :key="item.id" :label="item.title" :value="item.id" /></el-select></el-form-item>
          <el-form-item label="负责人"><el-select v-model="bugForm.owner_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="提出人"><el-select v-model="bugForm.reporter_id" clearable filterable><el-option v-for="user in users" :key="user.id" :label="user.full_name" :value="user.id" /></el-select></el-form-item>
          <el-form-item label="Bug 类型"><el-select v-model="bugForm.bug_type"><el-option v-for="option in bugTypeOptions" :key="option" :label="option" :value="option" /></el-select></el-form-item>
          <el-form-item label="严重程度"><el-select v-model="bugForm.severity"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item>
          <el-form-item label="优先级"><el-select v-model="bugForm.priority"><el-option v-for="option in priorityLevelOptions" :key="option.value" :label="option.label" :value="option.value"><RequirementPriorityBadge :value="option.value" /></el-option></el-select></el-form-item>
        </div>
        <el-form-item label="重现步骤"><RichTextPasteEditor v-model="bugForm.reproduce_steps" /></el-form-item>
        <el-form-item label="期望结果"><el-input v-model="bugForm.expected_result" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="实际结果"><el-input v-model="bugForm.actual_result" type="textarea" :rows="3" /></el-form-item>
      </el-form>

      <template v-else>
      <el-descriptions :column="3" border>
        <el-descriptions-item label="所属项目">{{ labelById(projects, bug.project_id) }}</el-descriptions-item>
        <el-descriptions-item label="关联需求">
          <router-link v-if="bug.requirement_id" class="table-link" :to="`/requirements/${bug.requirement_id}`">{{ labelById(requirements, bug.requirement_id, 'title') }}</router-link>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="来源用例">
          <router-link v-if="bug.test_case_id" class="table-link" :to="{ name: 'test-case-detail', params: { id: bug.test_case_id } }">{{ labelById(testCases, bug.test_case_id, 'title') }}</router-link>
          <span v-else>-</span>
        </el-descriptions-item>
        <el-descriptions-item label="负责人">{{ userLabel(users, bug.owner_id) }}</el-descriptions-item>
        <el-descriptions-item label="提出人">{{ userLabel(users, bug.reporter_id) }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ bugStatusLabel(bug.status) }}</el-descriptions-item>
        <el-descriptions-item label="严重程度"><RequirementPriorityBadge :value="bug.severity" /></el-descriptions-item>
        <el-descriptions-item label="优先级"><RequirementPriorityBadge :value="bug.priority" /></el-descriptions-item>
        <el-descriptions-item label="解决方案">{{ resolutionLabel(bug.resolution) }}</el-descriptions-item>
        <el-descriptions-item label="解决时间">{{ formatDateTime(bug.resolve_time) }}</el-descriptions-item>
        <el-descriptions-item label="验证结果">{{ bug.verify_result || '-' }}</el-descriptions-item>
        <el-descriptions-item label="重新打开次数">{{ bug.reopen_count ?? 0 }}</el-descriptions-item>
      </el-descriptions>

      <div class="detail-sections">
        <section class="detail-section">
          <h2>重现步骤</h2>
          <div class="rich-text" v-html="bug.reproduce_steps || '-'"></div>
        </section>
        <section class="detail-section">
          <h2>期望结果</h2>
          <div class="rich-text">{{ bug.expected_result || '-' }}</div>
        </section>
        <section class="detail-section">
          <h2>实际结果</h2>
          <div class="rich-text">{{ bug.actual_result || '-' }}</div>
        </section>
      </div>
      </template>
    </el-card>

        <CommitRecordsPanel object-type="bug" :object-id="bugId" />

<el-card shadow="never" class="detail-panel requirement-history-card">
      <template #header>历史记录</template>
      <div class="project-history requirement-history">
        <el-empty v-if="!history.length" description="暂无历史记录" />
        <div v-else class="project-history-list">
          <div v-for="(item, index) in history" :key="item.id" class="project-history-entry">
            <div class="project-history-line">
              <span class="project-history-index">{{ index + 1 }}</span>
              <span>{{ formatDateTime(item.effective_time || item.create_time) }}，由 {{ item.actor_name || '系统' }} {{ actionLabel(item.action) }}。</span>
            </div>
            <div class="project-history-detail">
              <div class="status-history-meta">
                {{ bugStatusLabel(item.from_status) }} -> {{ bugStatusLabel(item.to_status) }}
                <template v-if="item.reason"> · {{ item.reason }}</template>
              </div>
              <p v-if="item.remark">{{ item.remark }}</p>
            </div>
          </div>
        </div>
      </div>
    </el-card>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchBug, fetchBugStatusOperations, updateBug } from '../api/bugs'
import { fetchIterations } from '../api/iterations'
import { fetchProjects } from '../api/projects'
import { fetchRequirements } from '../api/requirements'
import { fetchTasks } from '../api/tasks'
import { fetchTestCases } from '../api/testCases'
import { fetchUsers } from '../api/users'
import CommitRecordsPanel from '../components/CommitRecordsPanel.vue'
import RequirementPriorityBadge from '../components/RequirementPriorityBadge.vue'
import RichTextPasteEditor from '../components/RichTextPasteEditor.vue'
import { labelById, userLabel } from '../utils/referenceLabels'

const route = useRoute()
const router = useRouter()
const bugId = computed(() => Number(route.params.id))
const loading = ref(false)
const saving = ref(false)
const editing = ref(false)
const bug = ref({})
const history = ref([])
const projects = ref([])
const iterations = ref([])
const requirements = ref([])
const tasks = ref([])
const testCases = ref([])
const users = ref([])
const bugForm = ref({})

const bugStatusOptions = [
  { label: '待确认', value: 'open' },
  { label: '修复中', value: 'fixing' },
  { label: '已解决', value: 'resolved' },
  { label: '待验证', value: 'verifying' },
  { label: '已关闭', value: 'closed' },
  { label: '重新打开', value: 'reopened' },
  { label: '已挂起', value: 'suspended' }
]
const resolutionOptions = ['设计如此', '重复Bug', '外部原因', '已解决', '无法重现', '延期处理', '不予解决']
const bugTypeOptions = ['代码错误', '配置相关', '安装部署', '安全相关', '性能问题', '标准规范', '测试脚本', '设计缺陷', '其他']
const priorityLevelOptions = [
  { label: '1级', value: '1' },
  { label: '2级', value: '2' },
  { label: '3级', value: '3' },
  { label: '4级', value: '4' },
  { label: '5级', value: '5' }
]
const actionOptions = [
  { label: '确认', value: 'confirm' },
  { label: '开始修复', value: 'start_fixing' },
  { label: '解决', value: 'resolve' },
  { label: '激活', value: 'activate' },
  { label: '挂起', value: 'suspend' },
  { label: '关闭', value: 'close' }
]

function optionLabel(options, value) {
  const option = options.find((item) => item.value === value)
  return option?.label || value || '-'
}
function bugStatusLabel(value) { return optionLabel(bugStatusOptions, value) }
function actionLabel(value) { return optionLabel(actionOptions, value) }
function resolutionLabel(value) { return resolutionOptions.includes(value) ? value : value || '-' }
function formatDateTime(value) { return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '-' }
function goBack() {
  if (route.query.from === 'dashboard') {
    router.push({ name: 'dashboard' })
    return
  }
  if (route.query.from === 'project' && bug.value.project_id) {
    router.push({ name: 'project-detail', params: { id: bug.value.project_id }, query: { tab: 'bugs' } })
    return
  }
  if (route.query.from === 'iteration' && route.query.iterationId) {
    router.push({ name: 'iteration-detail', params: { id: route.query.iterationId }, query: { tab: route.query.tab || 'bugs' } })
    return
  }
  router.push({ name: 'bugs' })
}

function fillBugForm() {
  bugForm.value = {
    project_id: bug.value.project_id || null,
    iteration_id: bug.value.iteration_id || null,
    requirement_id: bug.value.requirement_id || null,
    task_id: bug.value.task_id || null,
    test_case_id: bug.value.test_case_id || null,
    test_run_id: bug.value.test_run_id || null,
    title: bug.value.title || '',
    bug_type: bug.value.bug_type || '代码错误',
    severity: String(bug.value.severity || '3'),
    priority: String(bug.value.priority || '3'),
    owner_id: bug.value.owner_id || null,
    reporter_id: bug.value.reporter_id || null,
    reproduce_steps: bug.value.reproduce_steps || '',
    expected_result: bug.value.expected_result || '',
    actual_result: bug.value.actual_result || ''
  }
}
function startEdit() {
  fillBugForm()
  editing.value = true
}
function cancelEdit() {
  editing.value = false
  fillBugForm()
}
async function saveBug() {
  if (!bugForm.value.title.trim()) return ElMessage.warning('请填写 Bug 标题')
  saving.value = true
  try {
    await updateBug(bugId.value, {
      ...bugForm.value,
      project_id: bugForm.value.project_id || null,
      iteration_id: bugForm.value.iteration_id || null,
      requirement_id: bugForm.value.requirement_id || null,
      task_id: bugForm.value.task_id || null,
      test_case_id: bugForm.value.test_case_id || null,
      test_run_id: bugForm.value.test_run_id || null,
      owner_id: bugForm.value.owner_id || null,
      reporter_id: bugForm.value.reporter_id || null
    })
    editing.value = false
    await loadData()
    ElMessage.success('Bug 已保存')
  } finally {
    saving.value = false
  }
}

async function loadData() {
  loading.value = true
  try {
    const [bugRes, historyRes, projectRes, iterationRes, requirementRes, taskRes, testCaseRes, userRes] = await Promise.all([
      fetchBug(bugId.value),
      fetchBugStatusOperations(bugId.value),
      fetchProjects(),
      fetchIterations(),
      fetchRequirements(),
      fetchTasks(),
      fetchTestCases(),
      fetchUsers()
    ])
    bug.value = bugRes.data
    history.value = historyRes.data
    projects.value = projectRes.data
    iterations.value = iterationRes.data
    requirements.value = requirementRes.data
    tasks.value = taskRes.data
    testCases.value = testCaseRes.data
    users.value = userRes.data
    fillBugForm()
  } catch {
    ElMessage.error('Bug 详情加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
