import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref(null)

  const permissions = computed(() => user.value?.permissions || [])
  const displayName = computed(() => user.value?.username || '')
  const isAdmin = computed(() => permissions.value.includes('monitor:admin'))

  function setToken(value) {
    token.value = value
    localStorage.setItem('token', value)
  }
  function setUser(value) {
    user.value = value
  }
  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
  }

  return { token, user, permissions, displayName, isAdmin, setToken, setUser, logout }
})
