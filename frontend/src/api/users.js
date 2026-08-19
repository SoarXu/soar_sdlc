import { http } from './http'

export function fetchUsers() {
  return http.get('/users')
}

export function createUser(data) {
  return http.post('/users', data)
}

export function setUserSystemAdmin(userId, isSystemAdmin) {
  return http.put(`/users/${userId}/system-admin`, { is_system_admin: isSystemAdmin })
}

export function resetUserPassword(userId) {
  return http.post(`/users/${userId}/reset-password`)
}
