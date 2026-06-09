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
      <div class="current-project">
        <strong>SDLC 项目管理平台</strong>
        <span>API-backed / MySQL</span>
      </div>
      <el-menu router :default-active="$route.path" class="side-menu">
        <el-menu-item index="/">工作台</el-menu-item>
        <el-menu-item index="/programs">项目集</el-menu-item>
        <el-menu-item index="/projects">项目</el-menu-item>
        <el-menu-item index="/requirements">需求</el-menu-item>
        <el-menu-item index="/tasks">任务</el-menu-item>
        <el-menu-item index="/tests">测试管理</el-menu-item>
        <el-menu-item index="/bugs">Bug</el-menu-item>
        <el-menu-item index="/workflow">工作流配置</el-menu-item>
      </el-menu>
    </aside>

    <main class="main">
      <router-view />
    </main>
  </div>
</template>
