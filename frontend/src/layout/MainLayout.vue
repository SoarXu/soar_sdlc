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
            <span>{{ currentUsername }}</span>
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

    <main class="main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { computed } from 'vue'
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

const router = useRouter()
const authStore = useAuthStore()
const currentUsername = computed(() => localStorage.getItem('current_username') || '用户')

function handleUserCommand(command) {
  if (command === 'logout') {
    authStore.logout()
    router.push('/login')
  }
}
</script>
