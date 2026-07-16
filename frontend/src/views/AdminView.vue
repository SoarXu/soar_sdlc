<template>
  <div class="admin-overview-page">
    <section class="page-head">
      <div>
        <h1>&#21518;&#21488;&#31649;&#29702;</h1>
        <p>&#32479;&#19968;&#31649;&#29702;&#35282;&#33394;&#21644;&#24037;&#20316;&#27969;&#37197;&#32622;&#12290;</p>
      </div>
    </section>

    <section class="admin-overview-grid">
      <el-card
        v-for="module in adminModules"
        :key="module.key"
        class="admin-entry-card"
        shadow="hover"
        @click="openModule(module.path)"
      >
        <div class="admin-entry-card__head">
          <div class="admin-entry-icon">
            <el-icon v-if="module.key === 'roles'"><UserFilled /></el-icon>
            <el-icon v-else-if="module.key === 'workflow'"><Connection /></el-icon>
            <el-icon v-else><Setting /></el-icon>
          </div>
          <div>
            <h2>{{ module.title }}</h2>
            <p>{{ module.description }}</p>
          </div>
        </div>
      </el-card>
    </section>
  </div>
</template>

<script setup>
import { Connection, Setting, UserFilled } from '@element-plus/icons-vue'
import { useRouter } from 'vue-router'

import { adminModules } from '../utils/adminModules'

const router = useRouter()

function openModule(path) {
  router.push(path)
}
</script>
