import { http } from './http'
import { toWorkItemPatchPayload } from '../utils/workItemPatchPayload'

export function fetchRequirements() {
  return http.get('/requirements')
}

export function downloadRequirementImportTemplate(projectId) {
  return http.get('/requirements/import/template', {
    params: projectId ? { project_id: projectId } : undefined,
    responseType: 'blob'
  })
}

export async function exportRequirements(projectId) {
  try {
    return await http.get('/requirements/export', { params: { project_id: projectId }, responseType: 'blob', timeout: 120000 })
  } catch (error) {
    if (error?.response?.data instanceof Blob) {
      try {
        const data = JSON.parse(await error.response.data.text())
        error.apiMessage = data.detail?.message || (typeof data.detail === 'string' ? data.detail : '')
      } catch { /* Keep the original request error if the response is not JSON. */ }
    }
    error.apiMessage ||= '需求导出失败，请重试'
    throw error
  }
}

export function fetchRequirementImportProposers(query) {
  return http.get('/requirements/import/proposers', { params: { q: query || '' } })
}

export function previewRequirementImport(file, projectId, duplicateStrategy = 'update_existing', decisions = []) {
  const formData = new FormData()
  formData.append('file', file)
  if (projectId) formData.append('project_id', projectId)
  formData.append('duplicate_strategy', duplicateStrategy)
  formData.append('decisions', JSON.stringify(decisions))
  return http.post('/requirements/import/preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000
  })
}

export function commitRequirementImport(file, duplicateStrategy, projectId, previewToken, decisions = []) {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('duplicate_strategy', duplicateStrategy)
  if (projectId) formData.append('project_id', projectId)
  formData.append('preview_token', previewToken)
  formData.append('decisions', JSON.stringify(decisions))
  return http.post('/requirements/import/commit', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }, timeout: 120000
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
  return http.patch(`/requirements/${id}`, toWorkItemPatchPayload(payload))
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
