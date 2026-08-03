import axios from 'axios'
import { ElMessage } from 'element-plus'

import router from '../router'
import { createSessionExpirationHandler } from '../utils/sessionExpiration'

export const http = axios.create({
  baseURL: '/api/v1',
  timeout: 10000
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

const handleSessionExpired = createSessionExpirationHandler({
  storage: localStorage,
  notify: (message) => new Promise((resolve) => {
    ElMessage.warning({ message, onClose: resolve })
  }),
  navigate: (location) => window.location.replace(router.resolve(location).href),
  getCurrentPath: () => router.currentRoute.value.fullPath
})

http.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error?.response?.status === 401) {
      const sessionExpired = await handleSessionExpired(error?.config?.url)
      if (sessionExpired) error.sessionExpired = true
    }
    return Promise.reject(error)
  }
)
