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
      <el-menu router :default-active="$route.path" class="side-menu">
        <el-menu-item index="/">
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
        <el-menu-item index="/workflow">
          <el-icon><Setting /></el-icon>
          <span>工作流配置</span>
        </el-menu-item>
      </el-menu>
    </aside>

    <main class="main" :class="{ 'main-workbench': $route.path === '/' || $route.path === '/dashboard' }">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowDown,
  DataAnalysis,
  Folder,
  FolderOpened,
  Grid,
  Setting,
  Timer,
  Warning
} from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import { fetchUsers } from '../api/users'

const router = useRouter()
const authStore = useAuthStore()
const currentUsername = computed(() => localStorage.getItem('current_username') || '')
const currentFullName = ref(cachedFullNameForCurrentUser())
const currentDisplayName = computed(() => currentFullName.value || currentUsername.value || '未登录')

function handleUserCommand(command) {
  if (command === 'logout') {
    authStore.logout()
    router.push('/login')
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
