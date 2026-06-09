<template>
  <div class="app-shell">
    <header class="productbar">
      <div class="product-left">
        <span class="product-logo">IB</span>
        <span class="product-name">智享生物</span>
        <span class="product-subtitle">intellective bio</span>
      </div>
      <div class="product-right">
        <el-input class="global-search" placeholder="搜索需求、任务、Bug" size="small" />
        <span>消息</span>
        <span>帮助</span>
        <span>系统管理员</span>
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
        <el-menu-item index="/requirements">
          <el-icon><Document /></el-icon>
          <span>需求</span>
        </el-menu-item>
        <el-menu-item index="/tasks">
          <el-icon><Tickets /></el-icon>
          <span>任务</span>
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
import {
  DataAnalysis,
  Document,
  Folder,
  FolderOpened,
  Grid,
  Setting,
  Tickets,
  Timer,
  Warning
} from '@element-plus/icons-vue'
</script>
