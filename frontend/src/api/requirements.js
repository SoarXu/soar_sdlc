import { http } from './http'

export function fetchRequirements() {
  return http.get('/requirements')
}

export function downloadRequirementImportTemplate(projectId) {
  return http.get('/requirements/import/template', {
    params: projectId ? { project_id: projectId } : undefined,
    responseType: 'blob'
  })
}

export function previewRequirementImport(file, projectId) {
  const formData = new FormData()
  formData.append('file', file)
  if (projectId) formData.append('project_id', projectId)
  return http.post('/requirements/import/preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function commitRequirementImport(file, duplicateStrategy, projectId) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('duplicate_strategy', duplicateStrategy)
  if (projectId) formData.append('project_id', projectId)
  return http.post('/requirements/import/commit', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

export function fetchRequirement(id) {
  return http.get(`/requirements/${id}`)
}

export function fetchRequirementValidationCases(id) {
  return http.get(`/requirements/${id}/validation-cases`)
}

export function createRequirement(payload) {
  return http.post('/requirements', payload)
}

export function updateRequirement(id, payload) {
  return http.patch(`/requirements/${id}`, payload)
}

export function assignRequirement(id, payload) {
  return http.post(`/requirements/${id}/assign`, payload)
}

export function batchAssignRequirements(payload) {
  return http.post('/requirements/batch-assign', payload)
}

export function fetchRequirementStatusOperations(id) {
  return http.get(`/requirements/${id}/status-operations`)
}

export function fetchRequirementAuditLogs(id) {
  return http.get(`/requirements/${id}/audit-logs`)
}

export function deleteRequirement(id) {
  return http.delete(`/requirements/${id}`)
}

export function generateTask(requirementId, payload) {
  return http.post(`/requirements/${requirementId}/generate-task`, payload)
}
