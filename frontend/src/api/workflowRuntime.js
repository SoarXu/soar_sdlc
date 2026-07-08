import { http } from './http'

export function fetchWorkflowTransitions(objectType, id) {
  return http.get(`/workflow-runtime/${objectType}/${id}/transitions`)
}

export function fetchWorkflowTransitionsBatch(items) {
  return http.post('/workflow-runtime/transitions/batch', { items })
}

export function executeWorkflowTransition(objectType, id, payload) {
  return http.post(`/workflow-runtime/${objectType}/${id}/transition`, payload)
}
