<template>
  <div class="login-page">
    <el-card class="login-card">
      <h1>智享生物</h1>
      <p class="login-subtitle">intellective bio</p>
      <p class="login-hint">请输入账号密码登录。</p>

      <el-form label-position="top" @submit.prevent="handleLogin">
        <el-form-item label="账号">
          <el-input v-model="loginForm.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="loginForm.password" type="password" show-password />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="handleLogin">登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const loading = ref(false)
const loginForm = reactive({
  username: '',
  password: ''
})

async function handleLogin() {
  loading.value = true
  try {
    await authStore.login(loginForm.username, loginForm.password)
    ElMessage.success('登录成功')
    if (authStore.mustChangePassword) {
      router.push({ name: 'change-password', query: { redirect: loginRedirectPath() } })
      return
    }
    router.push(loginRedirectPath())
  } catch {
    ElMessage.error('登录失败，请确认账号密码和后端服务状态')
  } finally {
    loading.value = false
  }
}

function loginRedirectPath() {
  const redirect = Array.isArray(route.query.redirect) ? route.query.redirect[0] : route.query.redirect
  return redirect && redirect.startsWith('/') && !redirect.startsWith('//') ? redirect : '/'
}
</script>
