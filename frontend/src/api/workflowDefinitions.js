import { http } from './http'

export function fetchWorkflowDefinitions(params = {}) {
  return http.get('/workflow-definitions', { params })
}

export function createWorkflowDefinition(payload) {
  return http.post('/workflow-definitions', payload)
}

export function fetchWorkflowDefinitionGraph(id) {
  return http.get(`/workflow-definitions/${id}`)
}

export function saveWorkflowDefinitionGraph(id, payload) {
  return http.put(`/workflow-definitions/${id}/graph`, payload)
}

export function applyWorkflowDefinitionTemplate(id) {
  return http.post(`/workflow-definitions/${id}/apply-template`)
}

export function fetchWorkflowDefinitionTemplatePreview(id) {
  return http.get(`/workflow-definitions/${id}/template-preview`)
}
