<template>
  <div class="login-page">
    <el-card class="login-card">
      <h1>修改初始密码</h1>
      <p class="login-hint">首次登录前需要设置新的登录密码。</p>

      <el-form label-position="top" @submit.prevent="submit">
        <el-form-item label="当前密码" required>
          <el-input v-model="form.current_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="新密码" required>
          <el-input v-model="form.new_password" type="password" show-password />
        </el-form-item>
        <el-form-item label="确认新密码" required>
          <el-input v-model="confirmPassword" type="password" show-password />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="submit">确认修改</el-button>
        <el-button :disabled="loading" @click="logout">退出登录</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const loading = ref(false)
const confirmPassword = ref('')
const form = reactive({
  current_password: '',
  new_password: ''
})

async function submit() {
  if (!form.current_password || !form.new_password) return ElMessage.warning('请填写当前密码和新密码')
  if (form.new_password.length < 8) return ElMessage.warning('新密码至少 8 位')
  if (form.new_password !== confirmPassword.value) return ElMessage.warning('两次输入的新密码不一致')
  loading.value = true
  try {
    await authStore.changePassword({ ...form })
    ElMessage.success('密码已修改')
    router.push(redirectPath())
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '修改密码失败')
  } finally {
    loading.value = false
  }
}

function logout() {
  authStore.logout()
  router.push('/login')
}

function redirectPath() {
  const redirect = Array.isArray(route.query.redirect) ? route.query.redirect[0] : route.query.redirect
  return redirect && redirect.startsWith('/') && !redirect.startsWith('//') && redirect !== '/change-password'
    ? redirect
    : '/'
}
</script>
