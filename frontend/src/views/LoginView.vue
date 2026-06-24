<template>
  <div class="login-page">
    <el-card class="login-card">
      <h1>智享生物</h1>
      <p class="login-subtitle">intellective bio</p>
      <p class="login-hint">{{ isRegisterMode ? '创建账号后将自动登录。' : '请选择一个初始化用户，或手动输入账号密码。' }}</p>

      <template v-if="!isRegisterMode">
        <div class="login-users">
          <el-button v-for="item in demoUsers" :key="item.username" size="small" @click="fillUser(item)">
            {{ item.name }}
          </el-button>
        </div>

        <el-form label-position="top" @submit.prevent="handleLogin">
          <el-form-item label="账号">
            <el-input v-model="loginForm.username" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="loginForm.password" type="password" show-password />
          </el-form-item>
          <el-button type="primary" :loading="loading" @click="handleLogin">登录</el-button>
        </el-form>
      </template>

      <el-form v-else label-position="top" @submit.prevent="handleRegister">
        <el-form-item label="账号" required>
          <el-input v-model="registerForm.username" />
        </el-form-item>
        <el-form-item label="姓名" required>
          <el-input v-model="registerForm.full_name" />
        </el-form-item>
        <el-form-item label="密码" required>
          <el-input v-model="registerForm.password" type="password" show-password />
        </el-form-item>
        <div class="form-grid">
          <el-form-item label="邮箱">
            <el-input v-model="registerForm.email" />
          </el-form-item>
          <el-form-item label="手机号">
            <el-input v-model="registerForm.mobile" />
          </el-form-item>
        </div>
        <el-form-item label="部门">
          <el-input v-model="registerForm.department" />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="handleRegister">注册并登录</el-button>
      </el-form>

      <div class="login-switch">
        <el-button link type="primary" @click="isRegisterMode = !isRegisterMode">
          {{ isRegisterMode ? '已有账号，返回登录' : '没有账号？注册' }}
        </el-button>
      </div>
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
const isRegisterMode = ref(false)
const loginForm = reactive({
  username: 'admin',
  password: 'admin123'
})
const registerForm = reactive({
  username: '',
  full_name: '',
  password: '',
  email: '',
  mobile: '',
  department: ''
})

const demoUsers = [
  { name: '系统管理员', username: 'admin', password: 'admin123' },
  { name: '项目经理 陈序', username: 'pm_chen', password: 'User123456' },
  { name: '研发 林航', username: 'rd_lin', password: 'User123456' },
  { name: '测试 王晴', username: 'qa_wang', password: 'User123456' },
  { name: '产品 李澄', username: 'po_li', password: 'User123456' }
]

function fillUser(item) {
  loginForm.username = item.username
  loginForm.password = item.password
}

async function handleLogin() {
  loading.value = true
  try {
    await authStore.login(loginForm.username, loginForm.password)
    ElMessage.success('登录成功')
    router.push('/')
  } catch {
    ElMessage.error('登录失败，请确认账号密码和后端服务状态')
  } finally {
    loading.value = false
  }
}

async function handleRegister() {
  if (!registerForm.username.trim() || !registerForm.full_name.trim() || !registerForm.password.trim()) {
    return ElMessage.warning('请填写账号、姓名和密码')
  }
  loading.value = true
  try {
    await authStore.register({ ...registerForm })
    ElMessage.success('注册成功')
    router.push('/')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>
