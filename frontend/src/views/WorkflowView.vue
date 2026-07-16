<template>
  <section v-if="viewMode === 'list'">
    <div class="page-head">
      <div>
        <h1>工作流配置</h1>
        <p>维护工作流方案，点击方案名称进入详情页面编辑需求、任务、Bug 的流转和项目关联。</p>
      </div>
      <div class="page-actions">
        <el-button @click="backToAdmin">返回后台管理</el-button>
        <el-button v-if="canEditWorkflow" type="primary" @click="openCreate">新增方案</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <template #header>工作流方案列表</template>
      <el-table v-loading="loading" :data="configs" stripe>
        <el-table-column label="方案名称" min-width="180">
          <template #default="{ row }">
            <el-button link type="primary" class="table-link-button" @click="openDetail(row)">
              {{ row.name }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="description" label="说明" min-width="240" />
        <el-table-column label="状态" width="90">
          <template #default="{ row }">{{ row.enabled ? '启用' : '停用' }}</template>
        </el-table-column>
        <el-table-column label="关联项目" min-width="260">
          <template #default="{ row }">
            <div class="rule-project-tags">
              <el-tag v-for="project in projectsForConfig(row.id).slice(0, 4)" :key="project.id" effect="plain">
                {{ project.name }}
              </el-tag>
              <el-tag v-if="projectsForConfig(row.id).length > 4" type="info" effect="plain">
                +{{ projectsForConfig(row.id).length - 4 }}
              </el-tag>
              <span v-if="!projectsForConfig(row.id).length" class="muted-text">未关联项目</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column v-if="canEditWorkflow" label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-popconfirm title="确认停用该方案？" @confirm="removeConfig(row)">
              <template #reference><el-button link type="danger">停用</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>

  <section v-else>
    <div class="page-head">
      <div>
        <h1>{{ editingId ? '工作流方案详情' : '新增工作流方案' }}</h1>
        <p>一个方案内分别维护需求、任务、Bug 的可视化工作流，并绑定到项目后生效。</p>
      </div>
      <div class="page-actions">
        <el-button @click="backToAdmin">返回后台管理</el-button>
        <el-button @click="backToList">返回列表</el-button>
        <el-button v-if="canEditWorkflow" type="primary" :loading="saving" @click="saveDetail">保存</el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-form label-position="top">
        <el-form-item label="方案名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="状态">
          <el-switch v-model="form.enabled" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="editingId && canEditWorkflow" shadow="never" class="mt-16">
      <WorkflowDesigner
        :config-id="editingId"
        :config-name="form.name"
        :role-options="projectMemberRoleOptions"
      />
    </el-card>


    <el-card v-if="editingId" shadow="never" class="mt-16">
      <template #header>
        <div class="card-header-row">
          <span>已关联项目</span>
          <el-tag type="info" effect="plain">{{ linkedProjects.length }} 个项目</el-tag>
        </div>
      </template>
      <el-table :data="linkedProjects" stripe empty-text="未关联项目">
        <el-table-column prop="name" label="项目" min-width="180" />
        <el-table-column label="所属项目集" min-width="140">
          <template #default="{ row }">{{ programName(row.program_id) }}</template>
        </el-table-column>
        <el-table-column v-if="canEditWorkflow" label="切换到方案" min-width="220">
          <template #default="{ row }">
            <el-select
              v-model="transferTargets[row.id]"
              clearable
              filterable
              placeholder="选择目标方案"
              :disabled="projectUpdatingIds.has(row.id)"
            >
              <el-option
                v-for="config in transferConfigOptions"
                :key="config.id"
                :label="config.name"
                :value="config.id"
              />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column v-if="canEditWorkflow" label="操作" width="180" fixed="right">
          <template #default="{ row }">
            <el-button
              link
              type="primary"
              :loading="projectUpdatingIds.has(row.id)"
              :disabled="!transferTargets[row.id]"
              @click="transferProject(row)"
            >
              转移
            </el-button>
            <el-popconfirm title="确认取消该项目与当前方案的关联？" @confirm="unlinkProject(row)">
              <template #reference>
                <el-button link type="danger" :loading="projectUpdatingIds.has(row.id)">取消关联</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="canEditWorkflow" shadow="never" class="mt-16">
      <template #header>关联未配置工作流方案的项目</template>
      <div class="rule-project-toolbar">
        <span>未配置工作流方案的项目，可勾选后随方案一起保存。</span>
      </div>
      <el-table
        ref="projectLinkTableRef"
        :data="unassignedProjects"
        stripe
        max-height="420"
        row-key="id"
        @selection-change="onProjectSelectionChange"
      >
        <el-table-column type="selection" width="48" />
        <el-table-column prop="name" label="项目" min-width="180" />
        <el-table-column label="所属项目集" min-width="140">
          <template #default="{ row }">{{ programName(row.program_id) }}</template>
        </el-table-column>
      </el-table>
    </el-card>
  </section>

</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import {
  createAssigneeRuleConfig,
  deleteAssigneeRuleConfig,
  fetchAssigneeRuleConfigs,
  updateAssigneeRuleConfig
} from '../api/assigneeRuleConfigs'
import { fetchPrograms } from '../api/programs'
import { fetchProjects, updateProject } from '../api/projects'
import { fetchUsers } from '../api/users'
import WorkflowDesigner from '../components/WorkflowDesigner.vue'
import { showActionError } from '../utils/actionFeedback'
import { canConfigureWorkflow, currentUserFromStorage } from '../utils/permissions'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const configs = ref([])
const projects = ref([])
const programs = ref([])
const users = ref([])
const editingId = ref(null)
const viewMode = ref('list')
const selectedProjectIds = ref([])
const transferTargets = reactive({})
const projectUpdatingIds = ref(new Set())
const projectLinkTableRef = ref(null)
const currentUser = computed(() => currentUserFromStorage(users.value))
const canEditWorkflow = computed(() => canConfigureWorkflow(currentUser.value))
const projectMemberRoleOptions = [
  { label: '产品/需求负责人', value: 'product_owner' },
  { label: '产品经理', value: 'product_manager' },
  { label: '部门负责人', value: 'department_head' },
  { label: '开发主管', value: 'tech_lead' },
  { label: '开发主管', value: 'development_lead' },
  { label: '开发', value: 'developer' },
  { label: '测试主管', value: 'test_lead' },
  { label: '测试', value: 'tester' },
  { label: '访客', value: 'viewer' }
]
const form = reactive({
  name: '',
  description: '',
  requirement_owner_roles: '',
  task_owner_roles: '',
  test_case_tester_roles: '',
  test_run_owner_roles: '',
  bug_owner_roles: '',
  enabled: true
})
const unassignedProjects = computed(() => projects.value.filter((item) => !item.assignee_rule_config_id))
const linkedProjects = computed(() => projectsForConfig(editingId.value))
const transferConfigOptions = computed(() => {
  return configs.value.filter((item) => item.enabled && item.id !== editingId.value)
})

function backToAdmin() {
  router.push('/admin')
}

function resetForm() {
  editingId.value = null
  Object.assign(form, {
    name: '',
    description: '',
    requirement_owner_roles: '',
    task_owner_roles: '',
    test_case_tester_roles: '',
    test_run_owner_roles: '',
    bug_owner_roles: '',
    enabled: true
  })
  selectedProjectIds.value = []
  clearTransferTargets()
}

function openCreate() {
  resetForm()
  viewMode.value = 'detail'
  setTimeout(syncProjectSelection)
}

function openDetail(row) {
  editingId.value = row.id
  selectedProjectIds.value = []
  Object.assign(form, {
    name: row.name,
    description: row.description || '',
    requirement_owner_roles: '',
    task_owner_roles: '',
    test_case_tester_roles: '',
    test_run_owner_roles: '',
    bug_owner_roles: '',
    enabled: row.enabled
  })
  viewMode.value = 'detail'
  setTimeout(syncProjectSelection)
}

function backToList() {
  viewMode.value = 'list'
  resetForm()
}

async function loadData() {
  loading.value = true
  try {
    const [configRes, projectRes, programRes, userRes] = await Promise.all([
      fetchAssigneeRuleConfigs(),
      fetchProjects(),
      fetchPrograms(),
      fetchUsers()
    ])
    configs.value = configRes.data
    projects.value = projectRes.data
    programs.value = programRes.data
    users.value = userRes.data
    pruneTransferTargets()
  } finally {
    loading.value = false
  }
}

async function saveDetail() {
  if (!form.name.trim()) return ElMessage.warning('请填写方案名称')
  saving.value = true
  try {
    const payload = {
      ...form,
      requirement_owner_roles: '',
      task_owner_roles: '',
      test_case_tester_roles: '',
      test_run_owner_roles: '',
      bug_owner_roles: ''
    }
    const response = editingId.value
      ? await updateAssigneeRuleConfig(editingId.value, payload)
      : await createAssigneeRuleConfig(payload)
    const configId = editingId.value || response.data.id
    await bindSelectedProjects(configId)
    await loadData()
    editingId.value = configId
    ElMessage.success('工作流方案已保存')
  } catch (error) {
    showActionError(error, '工作流方案保存失败')
  } finally {
    saving.value = false
  }
}

async function removeConfig(row) {
  try {
    await deleteAssigneeRuleConfig(row.id)
    ElMessage.success('方案已停用')
    await loadData()
  } catch (error) {
    showActionError(error, '方案停用失败')
  }
}

async function bindSelectedProjects(configId) {
  const selectedIds = new Set(selectedProjectIds.value)
  const updates = unassignedProjects.value
    .filter((project) => selectedIds.has(project.id))
    .map((project) => {
      return updateProject(project.id, { assignee_rule_config_id: configId }).then(() => {
        project.assignee_rule_config_id = configId
      })
    })
  await Promise.all(updates)
}

async function transferProject(project) {
  const targetConfigId = transferTargets[project.id]
  if (!targetConfigId) return ElMessage.warning('请选择目标方案')
  try {
    await updateProjectRule(project, targetConfigId, '项目已切换到目标工作流方案')
    delete transferTargets[project.id]
  } catch (error) {
    showActionError(error, '项目切换工作流方案失败')
  }
}

async function unlinkProject(project) {
  try {
    await updateProjectRule(project, null, '项目已取消关联')
    delete transferTargets[project.id]
  } catch (error) {
    showActionError(error, '项目取消关联失败')
  }
}

async function updateProjectRule(project, configId, message) {
  if (projectUpdatingIds.value.has(project.id)) return
  projectUpdatingIds.value = new Set([...projectUpdatingIds.value, project.id])
  try {
    await updateProject(project.id, { assignee_rule_config_id: configId })
    project.assignee_rule_config_id = configId
    await loadData()
    ElMessage.success(message)
  } finally {
    const nextIds = new Set(projectUpdatingIds.value)
    nextIds.delete(project.id)
    projectUpdatingIds.value = nextIds
  }
}

function projectsForConfig(configId) {
  if (!configId) return []
  return projects.value.filter((item) => item.assignee_rule_config_id === configId)
}

function programName(programId) {
  return programs.value.find((item) => item.id === programId)?.name || '-'
}

function onProjectSelectionChange(rows) {
  selectedProjectIds.value = rows.map((item) => item.id)
}

function syncProjectSelection() {
  if (!projectLinkTableRef.value) return
  projectLinkTableRef.value.clearSelection()
  const selectedIds = new Set(selectedProjectIds.value)
  unassignedProjects.value.forEach((project) => {
    if (selectedIds.has(project.id)) projectLinkTableRef.value.toggleRowSelection(project, true)
  })
}

function clearTransferTargets() {
  Object.keys(transferTargets).forEach((key) => delete transferTargets[key])
}

function pruneTransferTargets() {
  const validProjectIds = new Set(projects.value.map((project) => String(project.id)))
  Object.keys(transferTargets).forEach((key) => {
    if (!validProjectIds.has(key)) delete transferTargets[key]
  })
}

onMounted(loadData)
</script>
