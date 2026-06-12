import { defineStore } from 'pinia'

import { login } from '../api/auth'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('access_token') || ''
  }),
  actions: {
    async login(username, password) {
      const { data } = await login({ username, password })
      this.token = data.access_token
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('current_username', data.username || username)
      localStorage.setItem('current_full_name', data.full_name || data.username || username)
      localStorage.setItem('current_full_name_username', data.username || username)
      if (data.user_id) localStorage.setItem('current_user_id', data.user_id)
    },
    logout() {
      this.token = ''
      localStorage.removeItem('access_token')
      localStorage.removeItem('current_username')
      localStorage.removeItem('current_full_name')
      localStorage.removeItem('current_full_name_username')
      localStorage.removeItem('current_user_id')
    }
  }
})
