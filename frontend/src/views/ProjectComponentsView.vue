<template>
  <section class="page-section" v-loading="loading">
    <div class="page-header">
      <div>
        <el-button link type="primary" @click="$router.push({ name: 'project-detail', params: { id: projectId } })">返回项目</el-button>
        <h1>{{ project.name || '项目' }}业务组件</h1>
      </div>
      <el-button v-if="!projectClosed" type="primary" @click="dialogVisible = true">从已关闭项目创建组件</el-button>
    </div>

    <el-table :data="components" stripe>
      <el-table-column prop="name" label="组件" min-width="180" />
      <el-table-column label="来源项目" min-width="180"><template #default="{ row }">{{ row.source_project_name_snapshot || '-' }}</template></el-table-column>
      <el-table-column label="成员" min-width="240"><template #default="{ row }">{{ memberLabel(row.members) }}</template></el-table-column>
      <el-table-column label="工作流方案" width="140"><template #default="{ row }">{{ row.workflow_scheme_id || '项目默认' }}</template></el-table-column>
      <el-table-column label="状态" width="100"><template #default="{ row }"><el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag></template></el-table-column>
    </el-table>

    <el-empty v-if="!loading && !components.length" description="暂无业务组件" />

    <el-dialog v-model="dialogVisible" title="从已关闭项目创建组件" width="520px" @closed="resetForm">
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
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createBusinessComponentFromProject, fetchBusinessComponents } from '../api/businessComponents'
import { fetchProject, fetchProjects } from '../api/projects'
import { fetchUsers } from '../api/users'

const route = useRoute()
const projectId = computed(() => Number(route.params.id))
const loading = ref(false)
const saving = ref(false)
const dialogVisible = ref(false)
const project = ref({})
const projects = ref([])
const components = ref([])
const users = ref([])
const form = reactive({ source_project_id: null, name: '', description: '' })
const projectClosed = computed(() => project.value.state_category === 'terminal')
const closedProjects = computed(() => projects.value.filter((item) => item.id !== projectId.value && item.state_category === 'terminal'))

function resetForm() {
  Object.assign(form, { source_project_id: null, name: '', description: '' })
}

function syncName(sourceProjectId) {
  const source = closedProjects.value.find((item) => item.id === sourceProjectId)
  if (source && !form.name) form.name = source.name
}

function memberLabel(members) {
  if (!members?.length) return '-'
  return members.map((member) => {
    const user = users.value.find((item) => item.id === member.user_id)
    return `${user?.full_name || user?.username || member.user_id} (${member.component_role})`
  }).join('、')
}

async function loadData() {
  loading.value = true
  try {
    const [projectRes, projectsRes, componentsRes, usersRes] = await Promise.all([
      fetchProject(projectId.value),
      fetchProjects(),
      fetchBusinessComponents(projectId.value),
      fetchUsers()
    ])
    project.value = projectRes.data
    projects.value = projectsRes.data
    components.value = componentsRes.data
    users.value = usersRes.data
  } finally {
    loading.value = false
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
    ElMessage.error(error?.response?.data?.detail || '创建业务组件失败')
  } finally {
    saving.value = false
  }
}

onMounted(loadData)
</script>
