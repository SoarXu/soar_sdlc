import { http } from './http'

export function fetchUsers() {
  return http.get('/users')
}

export function createUser(data) {
  return http.post('/users', data)
}

export function assignUserRoles(userId, roleIds) {
  return http.put(`/users/${userId}/roles`, { role_ids: roleIds })
}

export function resetUserPassword(userId) {
  return http.post(`/users/${userId}/reset-password`)
}
