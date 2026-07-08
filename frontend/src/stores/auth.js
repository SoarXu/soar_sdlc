import { defineStore } from 'pinia'

import { changePassword, login } from '../api/auth'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('access_token') || '',
    mustChangePassword: localStorage.getItem('must_change_password') === 'true'
  }),
  actions: {
    async login(username, password) {
      const { data } = await login({ username, password })
      this.applySession(data, username)
    },
    async changePassword(payload) {
      await changePassword(payload)
      this.mustChangePassword = false
      localStorage.setItem('must_change_password', 'false')
    },
    applySession(data, fallbackUsername) {
      this.token = data.access_token
      this.mustChangePassword = Boolean(data.must_change_password)
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('current_username', data.username || fallbackUsername)
      localStorage.setItem('current_full_name', data.full_name || data.username || fallbackUsername)
      localStorage.setItem('current_full_name_username', data.username || fallbackUsername)
      localStorage.setItem('must_change_password', String(Boolean(data.must_change_password)))
      if (data.user_id) localStorage.setItem('current_user_id', data.user_id)
    },
    logout() {
      this.token = ''
      this.mustChangePassword = false
      localStorage.removeItem('access_token')
      localStorage.removeItem('current_username')
      localStorage.removeItem('current_full_name')
      localStorage.removeItem('current_full_name_username')
      localStorage.removeItem('current_user_id')
      localStorage.removeItem('must_change_password')
    }
  }
})
