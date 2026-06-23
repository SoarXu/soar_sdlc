<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h1>DevOps</h1>
        <p>接入 GitLab 提交、Jenkins 任务和 Code Review。</p>
      </div>
      <el-button type="primary" @click="openCommitDialog">录入提交</el-button>
    </div>

    <el-tabs v-model="activeTab" class="devops-tabs">
      <el-tab-pane label="提交记录" name="commits">
        <el-table :data="commits" stripe>
          <el-table-column label="Commit" width="150">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDiff(row)">{{ row.short_sha || row.commit_sha }}</el-button>
            </template>
          </el-table-column>
          <el-table-column prop="title" label="提交说明" min-width="260" />
          <el-table-column prop="branch_name" label="分支" width="140" />
          <el-table-column prop="author_name" label="提交人" width="140" />
          <el-table-column label="状态" width="120">
            <template #default="{ row }">{{ reviewStatusLabel(row.review_status) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="160" fixed="right">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDiff(row)">查看 Diff</el-button>
              <el-button v-if="row.review_status !== 'reviewed'" link type="success" @click="reviewCommit(row)">已评审</el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="Code Review" name="reviews">
        <el-table :data="reviewTasks" stripe>
          <el-table-column prop="title" label="任务" min-width="260" />
          <el-table-column label="Commit" width="150">
            <template #default="{ row }">
              <el-button link type="primary" @click="openDiff({ id: row.commit_id })">{{ row.commit?.short_sha || row.commit_id }}</el-button>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120"><template #default="{ row }">{{ reviewStatusLabel(row.status) }}</template></el-table-column>
          <el-table-column label="操作" width="140"><template #default="{ row }"><el-button link type="primary" @click="openDiff({ id: row.commit_id })">Review</el-button></template></el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="GitLab 仓库" name="repositories">
        <div class="project-tab-toolbar"><el-button type="primary" @click="openRepositoryDialog">新增仓库</el-button></div>
        <el-table :data="repositories" stripe>
          <el-table-column prop="name" label="仓库名称" min-width="180" />
          <el-table-column prop="repository_url" label="仓库地址" min-width="260" show-overflow-tooltip />
          <el-table-column prop="external_project_id" label="GitLab Project ID" width="160" />
          <el-table-column prop="default_branch" label="默认分支" width="120" />
          <el-table-column label="操作" width="130"><template #default="{ row }"><el-button link type="primary" @click="editRepository(row)">编辑</el-button><el-button link type="danger" @click="removeRepository(row)">删除</el-button></template></el-table-column>
        </el-table>
      </el-tab-pane>

      <el-tab-pane label="Jenkins" name="jenkins">
        <div class="project-tab-toolbar"><el-button type="primary" @click="openJobDialog">新增 Job</el-button></div>
        <el-table :data="jenkinsJobs" stripe>
          <el-table-column prop="job_name" label="Job 名称" min-width="180" />
          <el-table-column prop="jenkins_url" label="Jenkins 地址" min-width="260" show-overflow-tooltip />
          <el-table-column label="仓库" min-width="180"><template #default="{ row }">{{ repoName(row.repository_id) }}</template></el-table-column>
          <el-table-column prop="branch_pattern" label="分支规则" width="160" />
          <el-table-column label="操作" width="130"><template #default="{ row }"><el-button link type="primary" @click="editJob(row)">编辑</el-button><el-button link type="danger" @click="removeJob(row)">删除</el-button></template></el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="commitDialogVisible" title="录入 GitLab Commit" width="760px">
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="仓库"><el-select v-model="commitForm.repository_id" clearable filterable><el-option v-for="repo in repositories" :key="repo.id" :label="repo.name" :value="repo.id" /></el-select></el-form-item>
          <el-form-item label="Commit SHA" required><el-input v-model="commitForm.commit_sha" /></el-form-item>
          <el-form-item label="分支"><el-input v-model="commitForm.branch_name" /></el-form-item>
          <el-form-item label="提交人"><el-input v-model="commitForm.author_name" /></el-form-item>
        </div>
        <el-form-item label="提交说明"><el-input v-model="commitForm.message" type="textarea" :rows="3" placeholder="例如：REQ-12 TASK-30 修复校验逻辑" /></el-form-item>
        <el-form-item label="Git Diff"><el-input v-model="commitForm.diff_text" type="textarea" :rows="8" placeholder="粘贴 git show 或 GitLab diff 内容" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="commitDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitCommit">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="diffDialogVisible" title="Code Review Diff" width="920px" class="diff-dialog">
      <div v-if="selectedCommit" class="commit-summary">
        <strong>{{ selectedCommit.short_sha || selectedCommit.commit_sha }}</strong>
        <span>{{ selectedCommit.title || selectedCommit.message }}</span>
      </div>
      <pre class="diff-viewer">{{ selectedCommit?.diff_text || formatDiffJson(selectedCommit?.diff_json) || '暂无 diff 内容' }}</pre>
      <template #footer><el-button @click="diffDialogVisible = false">关闭</el-button><el-button v-if="selectedCommit?.review_status !== 'reviewed'" type="success" @click="reviewCommit(selectedCommit)">标记已评审</el-button></template>
    </el-dialog>

    <el-dialog v-model="repositoryDialogVisible" :title="editingRepositoryId ? '编辑仓库' : '新增仓库'" width="560px">
      <el-form label-position="top">
        <el-form-item label="仓库名称" required><el-input v-model="repositoryForm.name" /></el-form-item>
        <el-form-item label="仓库地址"><el-input v-model="repositoryForm.repository_url" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="GitLab Project ID"><el-input v-model="repositoryForm.external_project_id" /></el-form-item>
          <el-form-item label="默认分支"><el-input v-model="repositoryForm.default_branch" /></el-form-item>
        </div>
      </el-form>
      <template #footer><el-button @click="repositoryDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRepository">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="jobDialogVisible" :title="editingJobId ? '编辑 Jenkins Job' : '新增 Jenkins Job'" width="560px">
      <el-form label-position="top">
        <el-form-item label="Job 名称" required><el-input v-model="jobForm.job_name" /></el-form-item>
        <el-form-item label="Jenkins 地址"><el-input v-model="jobForm.jenkins_url" /></el-form-item>
        <div class="form-grid">
          <el-form-item label="仓库"><el-select v-model="jobForm.repository_id" clearable filterable><el-option v-for="repo in repositories" :key="repo.id" :label="repo.name" :value="repo.id" /></el-select></el-form-item>
          <el-form-item label="分支规则"><el-input v-model="jobForm.branch_pattern" /></el-form-item>
        </div>
      </el-form>
      <template #footer><el-button @click="jobDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitJob">保存</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  createDevopsRepository,
  createJenkinsJob,
  deleteDevopsRepository,
  deleteJenkinsJob,
  fetchCodeReviewTasks,
  fetchDevopsCommit,
  fetchDevopsCommits,
  fetchDevopsRepositories,
  fetchJenkinsJobs,
  ingestDevopsCommit,
  markDevopsCommitReviewed,
  updateDevopsRepository,
  updateJenkinsJob
} from '../api/devops'

const activeTab = ref('commits')
const repositories = ref([])
const jenkinsJobs = ref([])
const commits = ref([])
const reviewTasks = ref([])
const selectedCommit = ref(null)
const saving = ref(false)
const commitDialogVisible = ref(false)
const diffDialogVisible = ref(false)
const repositoryDialogVisible = ref(false)
const jobDialogVisible = ref(false)
const editingRepositoryId = ref(null)
const editingJobId = ref(null)

const commitForm = reactive({ repository_id: null, commit_sha: '', branch_name: '', author_name: '', message: '', diff_text: '' })
const repositoryForm = reactive({ provider: 'gitlab', name: '', repository_url: '', external_project_id: '', default_branch: '', enabled: 1 })
const jobForm = reactive({ job_name: '', jenkins_url: '', repository_id: null, branch_pattern: '', enabled: 1 })

function reviewStatusLabel(value) { return { pending: '待评审', reviewed: '已评审' }[value] || value || '-' }
function repoName(id) { return repositories.value.find((repo) => repo.id === id)?.name || '-' }
function formatDiffJson(value) { return value ? JSON.stringify(value, null, 2) : '' }

function openCommitDialog() {
  Object.assign(commitForm, { repository_id: null, commit_sha: '', branch_name: '', author_name: '', message: '', diff_text: '' })
  commitDialogVisible.value = true
}

function openRepositoryDialog() {
  editingRepositoryId.value = null
  Object.assign(repositoryForm, { provider: 'gitlab', name: '', repository_url: '', external_project_id: '', default_branch: '', enabled: 1 })
  repositoryDialogVisible.value = true
}

function editRepository(row) {
  editingRepositoryId.value = row.id
  Object.assign(repositoryForm, row)
  repositoryDialogVisible.value = true
}

function openJobDialog() {
  editingJobId.value = null
  Object.assign(jobForm, { job_name: '', jenkins_url: '', repository_id: null, branch_pattern: '', enabled: 1 })
  jobDialogVisible.value = true
}

function editJob(row) {
  editingJobId.value = row.id
  Object.assign(jobForm, row)
  jobDialogVisible.value = true
}

async function submitCommit() {
  if (!commitForm.commit_sha.trim()) return ElMessage.warning('请填写 Commit SHA')
  saving.value = true
  try {
    await ingestDevopsCommit({ ...commitForm, repository_id: commitForm.repository_id || null })
    commitDialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}

async function submitRepository() {
  if (!repositoryForm.name.trim()) return ElMessage.warning('请填写仓库名称')
  saving.value = true
  try {
    const payload = { ...repositoryForm }
    if (editingRepositoryId.value) await updateDevopsRepository(editingRepositoryId.value, payload)
    else await createDevopsRepository(payload)
    repositoryDialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}

async function submitJob() {
  if (!jobForm.job_name.trim()) return ElMessage.warning('请填写 Job 名称')
  saving.value = true
  try {
    const payload = { ...jobForm, repository_id: jobForm.repository_id || null }
    if (editingJobId.value) await updateJenkinsJob(editingJobId.value, payload)
    else await createJenkinsJob(payload)
    jobDialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}

async function removeRepository(row) {
  await ElMessageBox.confirm(`确认删除仓库「${row.name}」？`, '提示', { type: 'warning' })
  await deleteDevopsRepository(row.id)
  await loadData()
}

async function removeJob(row) {
  await ElMessageBox.confirm(`确认删除 Jenkins Job「${row.job_name}」？`, '提示', { type: 'warning' })
  await deleteJenkinsJob(row.id)
  await loadData()
}

async function openDiff(row) {
  const { data } = await fetchDevopsCommit(row.id)
  selectedCommit.value = data
  diffDialogVisible.value = true
}

async function reviewCommit(row) {
  if (!row?.id) return
  await markDevopsCommitReviewed(row.id, {})
  ElMessage.success('已标记为评审完成')
  diffDialogVisible.value = false
  await loadData()
}

async function loadData() {
  const [repoRes, jobRes, commitRes, reviewRes] = await Promise.all([
    fetchDevopsRepositories(),
    fetchJenkinsJobs(),
    fetchDevopsCommits(),
    fetchCodeReviewTasks()
  ])
  repositories.value = repoRes.data
  jenkinsJobs.value = jobRes.data
  commits.value = commitRes.data
  reviewTasks.value = reviewRes.data
}

onMounted(loadData)
</script>
