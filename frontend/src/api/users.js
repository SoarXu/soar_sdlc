import { http } from './http'

export function fetchUsers() {
  return http.get('/users')
}
