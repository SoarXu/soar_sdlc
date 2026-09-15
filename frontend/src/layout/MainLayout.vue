<template>
  <div class="app-shell">
    <header class="productbar">
      <div class="product-left">
        <span class="product-logo">IB</span>
        <span class="product-name">智享生物</span>
        <span class="product-subtitle">intellective bio</span>
      </div>
      <div class="product-right">
        <el-dropdown trigger="click" @command="handleUserCommand">
          <button class="user-menu" type="button">
            <span>{{ currentDisplayName }}</span>
            <el-icon><ArrowDown /></el-icon>
          </button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <aside class="sidebar">
      <el-menu
        router
        :default-active="activeMenuIndex"
        class="side-menu"
      >
        <el-menu-item :index="workbenchTarget">
          <el-icon><Grid /></el-icon>
          <span>工作台</span>
        </el-menu-item>
        <el-menu-item index="/programs">
          <el-icon><Folder /></el-icon>
          <span>项目集</span>
        </el-menu-item>
        <el-menu-item index="/projects">
          <el-icon><FolderOpened /></el-icon>
          <span>项目</span>
        </el-menu-item>
        <el-menu-item index="/iterations">
          <el-icon><Timer /></el-icon>
          <span>迭代</span>
        </el-menu-item>
        <el-menu-item index="/tests">
          <el-icon><DataAnalysis /></el-icon>
          <span>测试管理</span>
        </el-menu-item>
        <el-menu-item index="/bugs">
          <el-icon><Warning /></el-icon>
          <span>Bug</span>
        </el-menu-item>
        <el-menu-item index="/devops">
          <el-icon><Connection /></el-icon>
          <span>DevOps</span>
        </el-menu-item>
        <el-menu-item index="/admin">
          <el-icon><Setting /></el-icon>
          <span>后台管理</span>
        </el-menu-item>
      </el-menu>
      <button class="sidebar-version" type="button" title="系统信息" @click="openVersionInfo">
        <el-icon><InfoFilled /></el-icon>
        <span>v{{ frontendVersion }}</span>
      </button>
    </aside>

    <main class="main" :class="{ 'main-workbench': route.path === '/' || route.path === '/dashboard' }">
      <router-view />
    </main>
    <el-dialog v-model="versionVisible" title="系统信息" width="420px" append-to-body class="version-dialog">
      <el-descriptions :column="1" border size="small">
        <el-descriptions-item label="前端版本">{{ frontendVersion }}</el-descriptions-item>
        <el-descriptions-item label="后端版本">{{ backendVersion?.app_version || '版本信息无法获取' }}</el-descriptions-item>
        <el-descriptions-item label="发布状态">
          <el-tag :type="versionStatus === '一致' ? 'success' : 'warning'" size="small">{{ versionLoading ? '检查中' : versionStatus }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
      <template #footer>
        <el-button :loading="versionLoading" @click="loadVersionInfo">刷新</el-button>
        <el-button @click="versionVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  ArrowDown,
  Connection,
  DataAnalysis,
  Folder,
  FolderOpened,
  Grid,
  InfoFilled,
  Setting,
  Timer,
  Warning
} from '@element-plus/icons-vue'

import { fetchUsers } from '../api/users'
import { fetchVersionInfo } from '../api/version'
import { useAuthStore } from '../stores/auth'
import { activeAdminMenuIndex } from '../utils/adminModules'
import { saveWorkbenchQuery, workbenchMenuTarget } from '../utils/workbenchSidebarState'
import { releaseStatus } from '../utils/versionStatus'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const currentUsername = computed(() => localStorage.getItem('current_username') || '')
const currentFullName = ref(cachedFullNameForCurrentUser())
const currentDisplayName = computed(() => currentFullName.value || currentUsername.value || '未登录')
const workbenchTarget = ref(workbenchMenuTarget())
const frontendVersion = import.meta.env.VITE_APP_VERSION || '1.0.0'
const versionVisible = ref(false)
const versionLoading = ref(false)
const backendVersion = ref(null)
const versionStatus = computed(() => releaseStatus(frontendVersion, backendVersion.value))
const activeMenuIndex = computed(() => {
  if (route.path === '/' || route.path === '/dashboard') return workbenchTarget.value
  return activeAdminMenuIndex(route.path) || route.path
})

watch(
  () => [route.path, route.query],
  ([path, query]) => {
    if (path === '/' || path === '/dashboard') {
      saveWorkbenchQuery(query)
      workbenchTarget.value = workbenchMenuTarget()
    }
  },
  { immediate: true, deep: true }
)

function handleUserCommand(command) {
  if (command === 'logout') {
    authStore.logout()
    router.push('/login')
  }
}

function openVersionInfo() {
  versionVisible.value = true
  void loadVersionInfo()
}

async function loadVersionInfo() {
  versionLoading.value = true
  backendVersion.value = null
  try {
    const { data } = await fetchVersionInfo()
    backendVersion.value = data
  } catch {
    backendVersion.value = null
  } finally {
    versionLoading.value = false
  }
}

async function loadCurrentUserName() {
  if (!currentUsername.value) return
  const cachedName = cachedFullNameForCurrentUser()
  if (cachedName) {
    currentFullName.value = cachedName
    return
  }
  try {
    const { data } = await fetchUsers()
    const user = data.find((item) => item.username === currentUsername.value)
    if (user?.full_name) {
      currentFullName.value = user.full_name
      localStorage.setItem('current_full_name', user.full_name)
      localStorage.setItem('current_full_name_username', user.username)
      localStorage.setItem('current_user_id', user.id)
    }
  } catch {
    currentFullName.value = currentUsername.value
  }
}

function cachedFullNameForCurrentUser() {
  const username = localStorage.getItem('current_username') || ''
  const cachedUsername = localStorage.getItem('current_full_name_username') || ''
  if (!username || username !== cachedUsername) return ''
  return localStorage.getItem('current_full_name') || ''
}

onMounted(loadCurrentUserName)
</script>
