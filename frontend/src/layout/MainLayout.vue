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
        <span>陈序</span>
      </div>
    </header>

    <aside class="sidebar">
      <div class="current-project">
        <strong>智享生物研发管理</strong>
        <span>intellective bio / SDLC</span>
      </div>
      <el-menu router :default-active="$route.path" class="side-menu">
        <el-menu-item index="/">项目集总览</el-menu-item>
        <el-menu-item index="/projects">项目管理</el-menu-item>
        <el-menu-item index="/demands">需求管理</el-menu-item>
        <el-menu-item index="/tasks">任务看板</el-menu-item>
        <el-menu-item index="/tests">测试管理</el-menu-item>
        <el-menu-item index="/bugs">Bug 管理</el-menu-item>
        <el-menu-item index="/workflow">工作流配置</el-menu-item>
      </el-menu>
    </aside>

    <main class="main">
      <router-view />
    </main>
  </div>
</template>
