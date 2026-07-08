import { http } from './http'

export function login(payload) {
  return http.post('/auth/login', payload)
}

export function changePassword(payload) {
  return http.post('/auth/change-password', payload)
}
