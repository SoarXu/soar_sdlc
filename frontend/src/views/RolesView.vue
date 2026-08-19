<template>
  <section class="page">
    <div class="page-head">
      <div>
        <h1>用户管理</h1>
        <p>维护系统用户、系统管理员权限和项目业务角色字典。</p>
      </div>
      <div class="page-actions">
        <el-button @click="backToAdmin">返回后台管理</el-button>
        <el-button v-if="isSystemAdmin && activeTab === 'users'" type="primary" @click="openCreateUser">新增用户</el-button>
        <el-button v-if="isSystemAdmin && activeTab === 'roles'" type="primary" @click="openCreateRole">新增角色</el-button>
      </div>
    </div>

    <el-alert v-if="!isSystemAdmin" class="user-admin-alert" type="info" show-icon :closable="false" title="当前账号不是系统管理员，仅可查看用户和角色信息。" />

    <el-tabs v-model="activeTab" class="role-tabs">
      <el-tab-pane label="用户" name="users">
        <el-card shadow="never">
          <el-table v-loading="loading" :data="users" stripe>
            <el-table-column prop="full_name" label="姓名" min-width="140" />
            <el-table-column prop="username" label="账号" min-width="140" />
            <el-table-column prop="department" label="部门" min-width="160" />
            <el-table-column label="系统管理员" width="130">
              <template #default="{ row }">
                <el-switch :model-value="row.is_system_admin" :disabled="!isSystemAdmin || row.id === currentUserId" @change="setSystemAdmin(row, $event)" />
              </template>
            </el-table-column>
            <el-table-column label="首次改密" width="110"><template #default="{ row }">{{ row.must_change_password ? '是' : '否' }}</template></el-table-column>
            <el-table-column v-if="isSystemAdmin" label="操作" width="120" fixed="right"><template #default="{ row }"><el-button link type="primary" @click="resetPassword(row)">重置密码</el-button></template></el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="角色" name="roles">
        <el-card shadow="never">
          <template #header>角色字典</template>
          <el-table v-loading="loading" :data="roles" stripe>
            <el-table-column prop="role_name" label="角色名称" min-width="160" />
            <el-table-column prop="description" label="描述" min-width="220" show-overflow-tooltip />
            <el-table-column label="系统角色" width="100"><template #default="{ row }">{{ row.is_system ? '是' : '否' }}</template></el-table-column>
            <el-table-column label="状态" width="100"><template #default="{ row }">{{ row.enabled ? '启用' : '停用' }}</template></el-table-column>
            <el-table-column v-if="isSystemAdmin" label="操作" width="150" fixed="right">
              <template #default="{ row }">
                <el-button link type="primary" @click="openEditRole(row)">编辑</el-button>
                <el-popconfirm title="确认停用该角色？" @confirm="removeRole(row)"><template #reference><el-button link type="danger">停用</el-button></template></el-popconfirm>
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-tab-pane>
    </el-tabs>

    <el-dialog v-model="roleDialogVisible" :title="editingRoleId ? '编辑角色' : '新增角色'" width="520px">
      <el-form label-position="top">
        <el-form-item label="角色名称" required><el-input v-model="roleForm.role_name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="roleForm.description" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="启用"><el-switch v-model="roleForm.enabled" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="roleDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitRole">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="userDialogVisible" title="新增用户" width="620px">
      <el-form label-position="top">
        <div class="form-grid">
          <el-form-item label="账号" required><el-input v-model="userForm.username" /></el-form-item>
          <el-form-item label="姓名" required><el-input v-model="userForm.full_name" /></el-form-item>
          <el-form-item label="邮箱"><el-input v-model="userForm.email" /></el-form-item>
          <el-form-item label="手机号"><el-input v-model="userForm.mobile" /></el-form-item>
        </div>
        <el-form-item label="部门"><el-input v-model="userForm.department" /></el-form-item>
        <el-form-item label="系统管理员"><el-switch v-model="userForm.is_system_admin" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="userDialogVisible = false">取消</el-button><el-button type="primary" :loading="saving" @click="submitUser">创建用户</el-button></template>
    </el-dialog>

    <el-dialog v-model="passwordDialogVisible" title="一次性初始密码" width="520px" :close-on-click-modal="false" @closed="loadData">
      <el-alert type="warning" show-icon :closable="false" title="该密码只显示一次，请立即复制并交给用户。用户首次登录后必须修改密码。" />
      <el-input class="one-time-password" :model-value="oneTimePassword" readonly><template #append><el-button @click="copyPassword">复制</el-button></template></el-input>
      <template #footer><el-button type="primary" @click="passwordDialogVisible = false">我已保存</el-button></template>
    </el-dialog>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

import { createRole, deleteRole, fetchRoles, updateRole } from '../api/roles'
import { createUser, fetchUsers, resetUserPassword, setUserSystemAdmin } from '../api/users'
import { actionErrorMessage } from '../utils/permissions'

const router = useRouter()
const loading = ref(false)
const saving = ref(false)
const activeTab = ref('users')
const users = ref([])
const roles = ref([])
const roleDialogVisible = ref(false)
const userDialogVisible = ref(false)
const passwordDialogVisible = ref(false)
const editingRoleId = ref(null)
const oneTimePassword = ref('')
const roleForm = reactive({ role_name: '', description: '', enabled: true })
const userForm = reactive({ username: '', full_name: '', email: '', mobile: '', department: '', is_system_admin: false })
const currentUserId = computed(() => Number(localStorage.getItem('current_user_id') || 0))
const currentUser = computed(() => users.value.find((user) => user.id === currentUserId.value))
const isSystemAdmin = computed(() => Boolean(currentUser.value?.is_system_admin))

function backToAdmin() { router.push('/admin') }
function openCreateUser() { Object.assign(userForm, { username: '', full_name: '', email: '', mobile: '', department: '', is_system_admin: false }); userDialogVisible.value = true }
function openCreateRole() { editingRoleId.value = null; Object.assign(roleForm, { role_name: '', description: '', enabled: true }); roleDialogVisible.value = true }
function openEditRole(row) { editingRoleId.value = row.id; Object.assign(roleForm, { role_name: row.role_name, description: row.description || '', enabled: row.enabled }); roleDialogVisible.value = true }

async function submitRole() {
  if (!roleForm.role_name.trim()) return ElMessage.warning('请填写角色名称')
  saving.value = true
  try {
    if (editingRoleId.value) await updateRole(editingRoleId.value, { ...roleForm })
    else await createRole({ ...roleForm })
    roleDialogVisible.value = false
    await loadData()
  } catch (error) { ElMessage.error(actionErrorMessage(error)) } finally { saving.value = false }
}

async function submitUser() {
  if (!userForm.username.trim() || !userForm.full_name.trim()) return ElMessage.warning('请填写账号和姓名')
  saving.value = true
  try {
    const { data } = await createUser({ ...userForm })
    upsertUser(data.user); oneTimePassword.value = data.initial_password; userDialogVisible.value = false; passwordDialogVisible.value = true
    await loadData()
  } catch (error) { ElMessage.error(actionErrorMessage(error)) } finally { saving.value = false }
}

async function setSystemAdmin(row, isSystemAdmin) {
  try { await setUserSystemAdmin(row.id, isSystemAdmin); ElMessage.success('系统管理员权限已更新'); await loadData() } catch (error) { ElMessage.error(actionErrorMessage(error)) }
}
async function removeRole(row) { await deleteRole(row.id); await loadData() }
async function resetPassword(row) {
  const { data } = await resetUserPassword(row.id)
  upsertUser(data.user); oneTimePassword.value = data.initial_password; passwordDialogVisible.value = true
  await loadData()
}
async function copyPassword() {
  try { await navigator.clipboard.writeText(oneTimePassword.value); ElMessage.success('密码已复制') } catch { ElMessage.error('复制失败，请手动选择密码') }
}
async function loadData() {
  loading.value = true
  try {
    const [userResponse, roleResponse] = await Promise.all([fetchUsers(), fetchRoles()])
    users.value = userResponse.data; roles.value = roleResponse.data
  } finally { loading.value = false }
}
function upsertUser(user) {
  if (!user?.id) return
  const index = users.value.findIndex((item) => item.id === user.id)
  if (index >= 0) users.value.splice(index, 1, user)
  else users.value.push(user)
}

onMounted(loadData)
</script>
