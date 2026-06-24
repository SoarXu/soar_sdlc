import { defineStore } from 'pinia'

import { login, register } from '../api/auth'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: localStorage.getItem('access_token') || ''
  }),
  actions: {
    async login(username, password) {
      const { data } = await login({ username, password })
      this.applySession(data, username)
    },
    async register(payload) {
      const { data } = await register(payload)
      this.applySession(data, payload.username)
    },
    applySession(data, fallbackUsername) {
      this.token = data.access_token
      localStorage.setItem('access_token', data.access_token)
      localStorage.setItem('current_username', data.username || fallbackUsername)
      localStorage.setItem('current_full_name', data.full_name || data.username || fallbackUsername)
      localStorage.setItem('current_full_name_username', data.username || fallbackUsername)
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
