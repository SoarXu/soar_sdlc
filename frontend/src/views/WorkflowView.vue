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
          <template #default="{ row }">
            <el-tag :type="lifecycleStatusMeta(row.lifecycle_status).type" effect="plain">
              {{ lifecycleStatusMeta(row.lifecycle_status).label }}
            </el-tag>
          </template>
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
        <el-table-column v-if="canEditWorkflow" label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.lifecycle_status === 'draft'"
              link
              type="primary"
              :loading="lifecycleBusyIds.has(row.id)"
              @click="enableConfig(row)"
            >启用</el-button>
            <el-popconfirm
              v-else-if="row.lifecycle_status === 'enabled'"
              title="确认停用该方案？"
              @confirm="disableConfig(row)"
            >
              <template #reference>
                <el-button link type="danger" :loading="lifecycleBusyIds.has(row.id)">停用</el-button>
              </template>
            </el-popconfirm>
            <span v-else class="muted-text">仅保留历史</span>
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
        <el-button
          v-if="editingId && form.lifecycle_status === 'draft' && canEditWorkflow"
          :loading="lifecycleBusyIds.has(editingId)"
          @click="enableConfig(currentConfig)"
        >启用</el-button>
        <el-popconfirm
          v-if="editingId && form.lifecycle_status === 'enabled' && canEditWorkflow"
          title="确认停用该方案？"
          @confirm="disableConfig(currentConfig)"
        >
          <template #reference>
            <el-button type="danger" plain :loading="lifecycleBusyIds.has(editingId)">停用</el-button>
          </template>
        </el-popconfirm>
        <el-button v-if="canEditWorkflow" type="primary" :loading="saving" @click="saveDetail">
          {{ editingId ? '保存' : '创建方案' }}
        </el-button>
      </div>
    </div>

    <el-card shadow="never">
      <el-form label-position="top">
        <template v-if="!editingId">
          <el-form-item label="创建方式" required>
            <el-segmented
              v-model="form.creation_mode"
              :options="[
                { label: '创建空白方案', value: 'blank' },
                { label: '从模板创建', value: 'template' }
              ]"
            />
          </el-form-item>
          <el-form-item v-if="form.creation_mode === 'template'" label="模板来源" required>
            <el-select
              v-model="form.template_source_value"
              filterable
              class="workflow-template-select"
              placeholder="选择系统模板或已有工作流方案"
            >
              <el-option-group v-for="group in templateSourceGroups" :key="group.label" :label="group.label">
                <el-option
                  v-for="source in group.options"
                  :key="source.value"
                  :label="source.name"
                  :value="source.value"
                >
                  <div class="workflow-template-option">
                    <span class="workflow-template-option__copy">
                      <strong>{{ source.name }}</strong>
                      <small>{{ source.description || '暂无说明' }}</small>
                    </span>
                    <el-tag size="small" effect="plain">{{ source.source_type_label }}</el-tag>
                    <span class="muted-text">{{ lifecycleStatusMeta(source.lifecycle_status).label }}</span>
                  </div>
                </el-option>
              </el-option-group>
            </el-select>
          </el-form-item>
        </template>
        <el-form-item label="方案名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item v-if="editingId" label="方案状态">
          <el-tag :type="lifecycleStatusMeta(form.lifecycle_status).type" effect="plain">
            {{ lifecycleStatusMeta(form.lifecycle_status).label }}
          </el-tag>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card v-if="editingId && canEditWorkflow" shadow="never" class="mt-16">
      <WorkflowDesigner
        :config-id="editingId"
        :config-name="form.name"
        :role-options="workflowExecutionRoleOptions"
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

    <el-card v-if="editingId && form.lifecycle_status === 'enabled' && canEditWorkflow" shadow="never" class="mt-16">
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

import {
  createAssigneeRuleConfig,
  disableAssigneeRuleConfig,
  enableAssigneeRuleConfig,
  fetchAssigneeRuleConfigTemplateSources,
  fetchAssigneeRuleConfigs,
  updateAssigneeRuleConfig
} from '../api/assigneeRuleConfigs'
import { fetchPrograms } from '../api/programs'
import { fetchProjects, updateProject } from '../api/projects'
import { fetchUsers } from '../api/users'
import WorkflowDesigner from '../components/WorkflowDesigner.vue'
import { showActionError } from '../utils/actionFeedback'
import { canConfigureWorkflow, currentUserFromStorage } from '../utils/permissions'
import {
  buildWorkflowSchemeCreatePayload,
  groupWorkflowTemplateSources,
  lifecycleStatusMeta,
  workflowSchemeActionErrorMessage
} from '../utils/workflowSchemeCreation'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const configs = ref([])
const templateSources = ref([])
const projects = ref([])
const programs = ref([])
const users = ref([])
const editingId = ref(null)
const viewMode = ref('list')
const selectedProjectIds = ref([])
const transferTargets = reactive({})
const projectUpdatingIds = ref(new Set())
const projectLinkTableRef = ref(null)
const lifecycleBusyIds = ref(new Set())
const currentUser = computed(() => currentUserFromStorage(users.value))
const canEditWorkflow = computed(() => canConfigureWorkflow(currentUser.value))
const currentConfig = computed(() => configs.value.find((item) => item.id === editingId.value) || null)
const templateSourceGroups = computed(() => groupWorkflowTemplateSources(templateSources.value))
const workflowExecutionRoleOptions = [
  { label: '系统管理员', value: 'system_admin' },
  { label: '项目负责人', value: 'project_owner' },
  { label: '项目成员', value: 'project_member' },
  { label: '当前处理人', value: 'current_handler' },
  { label: '当前负责人', value: 'owner' },
  { label: '创建人', value: 'creator' },
  { label: '需求提出人', value: 'proposer' },
  { label: '缺陷报告人', value: 'reporter' },
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
  lifecycle_status: 'draft',
  creation_mode: 'blank',
  template_source_value: ''
})
const unassignedProjects = computed(() => projects.value.filter((item) => !item.assignee_rule_config_id))
const linkedProjects = computed(() => projectsForConfig(editingId.value))
const transferConfigOptions = computed(() => {
  return configs.value.filter((item) => item.lifecycle_status === 'enabled' && item.id !== editingId.value)
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
    lifecycle_status: 'draft',
    creation_mode: 'blank',
    template_source_value: ''
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
    lifecycle_status: row.lifecycle_status,
    creation_mode: 'blank',
    template_source_value: ''
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
    const [configRes, templateSourceRes, projectRes, programRes, userRes] = await Promise.all([
      fetchAssigneeRuleConfigs(),
      fetchAssigneeRuleConfigTemplateSources(),
      fetchProjects(),
      fetchPrograms(),
      fetchUsers()
    ])
    configs.value = configRes.data
    templateSources.value = templateSourceRes.data
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
  if (form.creation_mode === 'template' && !form.template_source_value) {
    return ElMessage.warning('请选择模板来源')
  }
  saving.value = true
  try {
    const payload = editingId.value
      ? { name: form.name.trim(), description: form.description?.trim() || null }
      : buildWorkflowSchemeCreatePayload(form)
    const response = editingId.value
      ? await updateAssigneeRuleConfig(editingId.value, payload)
      : await createAssigneeRuleConfig(payload)
    const configId = editingId.value || response.data.id
    if (form.lifecycle_status === 'enabled') await bindSelectedProjects(configId)
    await loadData()
    editingId.value = configId
    form.lifecycle_status = response.data.lifecycle_status || form.lifecycle_status
    ElMessage.success('工作流方案已保存')
  } catch (error) {
    showActionError(error, '工作流方案保存失败')
  } finally {
    saving.value = false
  }
}

async function enableConfig(row) {
  if (!row || lifecycleBusyIds.value.has(row.id)) return
  setLifecycleBusy(row.id, true)
  try {
    await enableAssigneeRuleConfig(row.id)
    ElMessage.success('方案已启用')
    await loadData()
    if (editingId.value === row.id) form.lifecycle_status = 'enabled'
  } catch (error) {
    await ElMessageBox.alert(
      workflowSchemeActionErrorMessage(error, '方案启用失败'),
      '提示',
      { type: 'warning' }
    )
  } finally {
    setLifecycleBusy(row.id, false)
  }
}

async function disableConfig(row) {
  if (!row || lifecycleBusyIds.value.has(row.id)) return
  setLifecycleBusy(row.id, true)
  try {
    await disableAssigneeRuleConfig(row.id)
    ElMessage.success('方案已停用')
    await loadData()
    if (editingId.value === row.id) form.lifecycle_status = 'disabled'
  } catch (error) {
    const message = workflowSchemeActionErrorMessage(error, '方案停用失败')
    await ElMessageBox.alert(message, '提示', { type: 'warning' })
  } finally {
    setLifecycleBusy(row.id, false)
  }
}

function setLifecycleBusy(id, busy) {
  const next = new Set(lifecycleBusyIds.value)
  if (busy) next.add(id)
  else next.delete(id)
  lifecycleBusyIds.value = next
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
