import { http } from './http'

export function fetchWorkflowRules() {
  return http.get('/workflow-rules')
}

export function createWorkflowRule(payload) {
  return http.post('/workflow-rules', payload)
}

export function updateWorkflowRule(id, payload) {
  return http.patch(`/workflow-rules/${id}`, payload)
}

export function deleteWorkflowRule(id) {
  return http.delete(`/workflow-rules/${id}`)
}

export function fetchWorkflowComponents() {
  return http.get('/workflow-rules/components')
}

export function fetchWorkflowTemplates() {
  return http.get('/workflow-rules/templates')
}

export function fetchWorkflowComponentRegistry() {
  return http.get('/workflow-components')
}

export function createWorkflowComponent(payload) {
  return http.post('/workflow-components', payload)
}

export function updateWorkflowComponent(id, payload) {
  return http.patch(`/workflow-components/${id}`, payload)
}

export function deleteWorkflowComponent(id) {
  return http.delete(`/workflow-components/${id}`)
}

export function fetchWorkflowHandlers() {
  return http.get('/workflow-handlers')
}
