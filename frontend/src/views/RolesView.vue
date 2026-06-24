<template>
  <section class="page">
    <div class="page-header">
      <div>
        <h1>角色管理</h1>
        <p>维护业务角色，并给用户分配角色。</p>
      </div>
      <el-button type="primary" @click="openCreateRole">新增角色</el-button>
    </div>

    <el-card shadow="never">
      <template #header>角色列表</template>
      <el-table v-loading="loading" :data="roles" stripe>
        <el-table-column prop="role_name" label="角色名称" min-width="160" />
        <el-table-column prop="role_key" label="角色标识" min-width="160" />
        <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
        <el-table-column label="系统角色" width="100"><template #default="{ row }">{{ row.is_system ? '是' : '否' }}</template></el-table-column>
        <el-table-column label="状态" width="100"><template #default="{ row }">{{ row.enabled ? '启用' : '停用' }}</template></el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openEditRole(row)">编辑</el-button>
            <el-popconfirm title="确认停用该角色？" @confirm="removeRole(row)">
              <template #reference><el-button link type="danger">停用</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card shadow="never" class="role-users-card">
      <template #header>用户角色分配</template>
      <el-table :data="users" stripe>
        <el-table-column prop="full_name" label="姓名" min-width="140" />
        <el-table-column prop="username" label="账号" min-width="140" />
        <el-table-column prop="department" label="部门" min-width="160" />
        <el-table-column label="角色" min-width="280">
          <template #default="{ row }">
            <el-select
              :model-value="row.roles.map(role => role.id)"
              multiple
              filterable
              collapse-tags
              collapse-tags-tooltip
              @change="assignRoles(row, $event)"
            >
              <el-option v-for="role in enabledRoles" :key="role.id" :label="role.role_name" :value="role.id" />
            </el-select>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="roleDialogVisible" :title="editingRoleId ? '编辑角色' : '新增角色'" width="520px">
      <el-form label-position="top">
        <el-form-item label="角色名称" required><el-input v-model="roleForm.role_name" /></el-form-item>
        <el-form-item label="角色标识" required><el-input v-model="roleForm.role_key" :disabled="Boolean(editingRoleId)" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="roleForm.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="roleForm.enabled" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="roleDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitRole">保存</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'

import { createRole, deleteRole, fetchRoles, updateRole } from '../api/roles'
import { assignUserRoles, fetchUsers } from '../api/users'

const loading = ref(false)
const saving = ref(false)
const roles = ref([])
const users = ref([])
const roleDialogVisible = ref(false)
const editingRoleId = ref(null)
const roleForm = reactive({ role_key: '', role_name: '', description: '', enabled: true })
const enabledRoles = computed(() => roles.value.filter((role) => role.enabled))

function openCreateRole() {
  editingRoleId.value = null
  Object.assign(roleForm, { role_key: '', role_name: '', description: '', enabled: true })
  roleDialogVisible.value = true
}

function openEditRole(row) {
  editingRoleId.value = row.id
  Object.assign(roleForm, {
    role_key: row.role_key,
    role_name: row.role_name,
    description: row.description || '',
    enabled: row.enabled
  })
  roleDialogVisible.value = true
}

async function submitRole() {
  if (!roleForm.role_key.trim() || !roleForm.role_name.trim()) return ElMessage.warning('请填写角色名称和标识')
  saving.value = true
  try {
    if (editingRoleId.value) await updateRole(editingRoleId.value, { ...roleForm })
    else await createRole({ ...roleForm })
    roleDialogVisible.value = false
    await loadData()
  } finally {
    saving.value = false
  }
}

async function removeRole(row) {
  await deleteRole(row.id)
  await loadData()
}

async function assignRoles(row, roleIds) {
  await assignUserRoles(row.id, roleIds)
  ElMessage.success('角色已更新')
  await loadData()
}

async function loadData() {
  loading.value = true
  try {
    const [roleRes, userRes] = await Promise.all([fetchRoles(), fetchUsers()])
    roles.value = roleRes.data
    users.value = userRes.data
  } finally {
    loading.value = false
  }
}

onMounted(loadData)
</script>
