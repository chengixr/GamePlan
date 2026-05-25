import { defineStore } from 'pinia'
import { api } from '../api'

export const useAuthStore = defineStore('auth', {
  state: () => ({ user: null }),
  actions: {
    async checkAuth() {
      try { this.user = await api.me() } catch { this.user = null }
    },
    async login(username, password) {
      this.user = await api.login({ username, password })
    },
    async register(username, password) {
      this.user = await api.register({ username, password })
    },
    async logout() {
      await api.logout()
      this.user = null
    },
    async updateProfile(body) {
      this.user = await api.updateProfile(body)
    },
    async changePassword(body) {
      await api.changePassword(body)
    },
  },
})
