import { http } from './http'

export function fetchExceptionRules() {
  return http.get('/exception-rules')
}

export function createExceptionRule(payload) {
  return http.post('/exception-rules', payload)
}

export function updateExceptionRule(id, payload) {
  return http.patch(`/exception-rules/${id}`, payload)
}

export function deleteExceptionRule(id) {
  return http.delete(`/exception-rules/${id}`)
}
