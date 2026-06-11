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
      localStorage.setItem('current_username', username)
    },
    logout() {
      this.token = ''
      localStorage.removeItem('access_token')
      localStorage.removeItem('current_username')
    }
  }
})
