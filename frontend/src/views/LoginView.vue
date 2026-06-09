<template>
  <div class="login-page">
    <el-card class="login-card">
      <h1>智享生物</h1>
      <p class="login-subtitle">intellective bio</p>
      <p class="login-hint">请选择一个初始化用户，或手动输入账号密码。</p>

      <div class="login-users">
        <el-button v-for="item in demoUsers" :key="item.username" size="small" @click="fillUser(item)">
          {{ item.name }}
        </el-button>
      </div>

      <el-form label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="账号">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="handleLogin">登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const form = reactive({
  username: 'admin',
  password: 'admin123'
})

const demoUsers = [
  { name: '系统管理员', username: 'admin', password: 'admin123' },
  { name: '项目经理 陈序', username: 'pm_chen', password: 'User123456' },
  { name: '研发 林航', username: 'rd_lin', password: 'User123456' },
  { name: '测试 王晴', username: 'qa_wang', password: 'User123456' },
  { name: '产品 李澄', username: 'po_li', password: 'User123456' }
]

function fillUser(item) {
  form.username = item.username
  form.password = item.password
}

async function handleLogin() {
  loading.value = true
  try {
    await authStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push('/')
  } catch (error) {
    ElMessage.error('登录失败，请确认账号密码和后端服务状态')
  } finally {
    loading.value = false
  }
}
</script>
