<template>
  <section>
    <div class="page-head">
      <div>
        <h1>项目集总览</h1>
        <p>用更少层级管理项目、需求、交付与质量。</p>
      </div>
      <el-button type="primary">新增项目集</el-button>
    </div>

    <div class="metrics">
      <el-card v-for="item in metrics" :key="item.label" shadow="never">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </el-card>
    </div>

    <el-card shadow="never">
      <template #header>工作台</template>
      <el-table :data="rows" stripe>
        <el-table-column prop="name" label="项目集" />
        <el-table-column prop="owner" label="负责人" width="140" />
        <el-table-column prop="projects" label="项目数" width="120" />
        <el-table-column prop="health" label="健康度" width="140" />
      </el-table>
    </el-card>
  </section>
</template>

<script setup>
const metrics = [
  { label: '项目集', value: 2 },
  { label: '需求', value: 24 },
  { label: '任务完成', value: '18/32' },
  { label: '未关闭 Bug', value: 6 }
]

const rows = [
  { name: '智享研发平台', owner: '陈序', projects: 2, health: '78%' },
  { name: '临床协作套件', owner: '林舟', projects: 1, health: '63%' }
]
</script>
