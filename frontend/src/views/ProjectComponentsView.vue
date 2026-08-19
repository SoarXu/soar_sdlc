<template>
  <section class="page-section" v-loading="loading">
    <div v-if="!embedded" class="page-header">
      <div>
        <el-button link type="primary" @click="$router.push({ name: 'project-detail', params: { id: projectId } })">返回项目</el-button>
        <h1>{{ project.name || '项目' }}业务组件</h1>
      </div>
      <el-button v-if="!projectClosed" type="primary" @click="dialogVisible = true">创建组件</el-button>
    </div>
    <el-button v-else-if="!projectClosed" type="primary" @click="dialogVisible = true">创建组件</el-button>

    <el-table :data="components" stripe>
      <el-table-column prop="name" label="组件" min-width="180" />
      <el-table-column label="来源项目" min-width="180"><template #default="{ row }">{{ row.source_project_name_snapshot || '-' }}</template></el-table-column>
      <el-table-column label="成员" min-width="240"><template #default="{ row }">{{ memberLabel(row.members) }}</template></el-table-column>
      <el-table-column label="工作流方案" min-width="180"><template #default="{ row }">{{ workflowSchemeLabel(row.workflow_scheme_id) }}</template></el-table-column>
      <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
      <el-table-column v-if="!projectClosed" label="操作" fixed="right" width="88">
        <template #default="{ row }"><el-button link type="primary" @click="openEditDialog(row)">编辑</el-button></template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && !components.length" description="暂无业务组件" />

    <el-dialog v-model="dialogVisible" title="创建组件" width="520px" @closed="resetForm">
      <el-form label-width="100px">
        <el-form-item label="来源项目" required>
          <el-select v-model="form.source_project_id" filterable class="form-select" @change="syncName">
            <el-option v-for="item in closedProjects" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="组件名称" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialogVisible" title="编辑业务组件" width="680px" @closed="resetEditForm">
      <el-form label-width="100px">
        <el-form-item label="组件名称" required><el-input v-model="editForm.name" /></el-form-item>
        <el-form-item label="说明"><el-input v-model="editForm.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="工作流方案">
          <el-select v-model="editForm.workflow_scheme_id" clearable filterable class="form-select" placeholder="请选择工作流方案">
            <el-option v-for="scheme in enabledWorkflowSchemes" :key="scheme.id" :label="scheme.name" :value="scheme.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态"><el-switch v-model="editForm.enabled" active-text="启用" inactive-text="停用" /></el-form-item>
        <el-form-item label="组件成员">
          <div class="component-members-editor">
            <div v-for="(member, index) in editForm.members" :key="`${member.user_id}-${index}`" class="component-member-row">
              <el-select v-model="member.user_id" filterable placeholder="选择成员">
                <el-option v-for="user in projectUsers" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
              </el-select>
              <el-select v-model="member.component_role" filterable placeholder="选择项目角色">
                <el-option v-for="role in projectRoleOptions(member.user_id)" :key="role.value" :label="role.label" :value="role.value" />
              </el-select>
              <el-button link type="danger" @click="removeEditMember(index)">删除</el-button>
            </div>
            <el-button link type="primary" @click="addEditMember">新增成员</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="saveComponent">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createBusinessComponentFromProject, fetchBusinessComponents, saveBusinessComponentMembers, updateBusinessComponent } from '../api/businessComponents'
import { fetchProject, fetchProjectMembers, fetchProjects } from '../api/projects'
import { fetchUsers } from '../api/users'
import { fetchAssigneeRuleConfigs } from '../api/assigneeRuleConfigs'
import { actionErrorMessage } from '../utils/permissions'

const props = defineProps({
  projectId: { type: Number, default: null },
  embedded: { type: Boolean, default: false }
})
const route = useRoute()
const projectId = computed(() => props.projectId || Number(route.params.id))
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const editDialogVisible = ref(false)
const project = ref({})
const projects = ref([])
const components = ref([])
const users = ref([])
const projectMembers = ref([])
const workflowSchemes = ref([])
const form = reactive({ source_project_id: null, name: '', description: '' })
const editForm = reactive({ id: null, name: '', description: '', workflow_scheme_id: null, enabled: true, members: [] })
const projectClosed = computed(() => project.value.state_category === 'terminal')
const closedProjects = computed(() => projects.value.filter((item) => item.id !== projectId.value && item.state_category === 'terminal'))
const enabledWorkflowSchemes = computed(() => workflowSchemes.value.filter((item) => item.lifecycle_status === 'enabled'))
const projectUsers = computed(() => {
  const memberIds = new Set(projectMembers.value.map((item) => item.user_id))
  return users.value.filter((item) => memberIds.has(item.id))
})
function resetForm() {
  Object.assign(form, { source_project_id: null, name: '', description: '' })
}

function syncName(sourceProjectId) {
  const source = closedProjects.value.find((item) => item.id === sourceProjectId)
  if (source && !form.name) form.name = source.name
}

function workflowSchemeLabel(schemeId) {
  if (!schemeId) return '项目默认'
  return workflowSchemes.value.find((item) => item.id === schemeId)?.name || '工作流方案不可用'
}

function resetEditForm() {
  Object.assign(editForm, { id: null, name: '', description: '', workflow_scheme_id: null, enabled: true, members: [] })
}

function openEditDialog(component) {
  Object.assign(editForm, {
    id: component.id,
    name: component.name,
    description: component.description || '',
    workflow_scheme_id: component.workflow_scheme_id || null,
    enabled: component.enabled,
    members: (component.members || []).map((member) => ({ user_id: member.user_id, component_role: member.component_role }))
  })
  editDialogVisible.value = true
}

function addEditMember() {
  editForm.members.push({ user_id: null, component_role: null })
}

function removeEditMember(index) {
  editForm.members.splice(index, 1)
}

function memberLabel(members) {
  if (!members?.length) return '-'
  return members.map((member) => {
    const user = users.value.find((item) => item.id === member.user_id)
    return `${user?.full_name || user?.username || member.user_id} (${backendRoleLabel(member.component_role)})`
  }).join('、')
}

function backendRoleLabel(roleKey) {
  return projectRoleOptions().find((role) => role.value === roleKey)?.label || roleKey
}

function projectRoleOptions(userId = null) {
  const roles = projectMembers.value
    .filter((member) => !userId || member.user_id === userId)
    .map((member) => member.project_role)
  return [...new Set(roles)].map((role) => ({ value: role, label: projectRoleLabel(role) }))
}

function projectRoleLabel(role) {
  return ({ project_owner: '项目负责人', product_manager: '产品经理', development_lead: '开发主管', developer: '开发', tester: '测试', viewer: '访客' })[role] || role
}

async function loadData() {
  loading.value = true
  try {
    const [projectRes, projectsRes, componentsRes, usersRes, membersRes, schemesRes] = await Promise.all([
      fetchProject(projectId.value),
      fetchProjects(),
      fetchBusinessComponents(projectId.value),
      fetchUsers(),
      fetchProjectMembers(projectId.value),
      fetchAssigneeRuleConfigs()
    ])
    project.value = projectRes.data
    projects.value = projectsRes.data
    components.value = componentsRes.data
    users.value = usersRes.data
    projectMembers.value = membersRes.data
    workflowSchemes.value = schemesRes.data
  } finally {
    loading.value = false
  }
}

async function saveComponent() {
  if (!editForm.name.trim()) return ElMessage.warning('请填写组件名称')
  if (editForm.members.some((member) => !member.user_id || !member.component_role)) return ElMessage.warning('请选择组件成员和后台角色')
  if (new Set(editForm.members.map((member) => member.user_id)).size !== editForm.members.length) return ElMessage.warning('组件成员不可重复')
  if (editForm.members.some((member) => !projectRoleOptions(member.user_id).some((role) => role.value === member.component_role))) return ElMessage.warning('请选择该成员在当前项目中的角色')
  saving.value = true
  try {
    await updateBusinessComponent(projectId.value, editForm.id, {
      name: editForm.name.trim(),
      description: editForm.description || null,
      workflow_scheme_id: editForm.workflow_scheme_id,
      enabled: editForm.enabled
    })
    await saveBusinessComponentMembers(projectId.value, editForm.id, editForm.members)
    ElMessage.success('业务组件已保存')
    editDialogVisible.value = false
    await loadData()
  } catch (error) {
    ElMessage.error(actionErrorMessage(error))
  } finally {
    saving.value = false
  }
}

async function submit() {
  if (!form.source_project_id || !form.name.trim()) return ElMessage.warning('请选择来源项目并填写组件名称')
  saving.value = true
  try {
    await createBusinessComponentFromProject(projectId.value, { ...form, name: form.name.trim() })
    ElMessage.success('业务组件已创建')
    dialogVisible.value = false
    await loadData()
  } catch (error) {
    ElMessage.error(actionErrorMessage(error))
  } finally {
    saving.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
.component-members-editor {
  display: grid;
  gap: 8px;
  width: 100%;
}

.component-member-row {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(140px, 0.8fr) auto;
  align-items: center;
  gap: 8px;
}
</style>
