import { http } from './http'

export function fetchHandlerTransitionRules(params = {}) {
  return http.get('/handler-transition-rules', { params })
}

export function createHandlerTransitionRule(payload) {
  return http.post('/handler-transition-rules', payload)
}

export function updateHandlerTransitionRule(id, payload) {
  return http.patch(`/handler-transition-rules/${id}`, payload)
}

export function deleteHandlerTransitionRule(id) {
  return http.delete(`/handler-transition-rules/${id}`)
}
