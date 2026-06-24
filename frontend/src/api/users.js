import { http } from './http'

export function fetchUsers() {
  return http.get('/users')
}

export function assignUserRoles(userId, roleIds) {
  return http.put(`/users/${userId}/roles`, { role_ids: roleIds })
}
