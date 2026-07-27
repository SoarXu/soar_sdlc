import { http } from './http'

export function fetchBusinessComponents(projectId) {
  return http.get(`/projects/${projectId}/business-components`)
}

export function createBusinessComponentFromProject(projectId, payload) {
  return http.post(`/projects/${projectId}/business-components/from-project`, payload)
}

export function saveBusinessComponentMembers(projectId, componentId, payload) {
  return http.put(`/projects/${projectId}/business-components/${componentId}/members`, payload)
}

export function updateBusinessComponent(projectId, componentId, payload) {
  return http.patch(`/projects/${projectId}/business-components/${componentId}`, payload)
}

export function fetchBusinessComponentRoutes(projectId, componentId) {
  return http.get(`/projects/${projectId}/business-components/${componentId}/transition-routes`)
}

export function saveBusinessComponentRoutes(projectId, componentId, payload) {
  return http.put(`/projects/${projectId}/business-components/${componentId}/transition-routes`, payload)
}

export function migrateBusinessComponentWorkItem(projectId, componentId, objectType, objectId, payload) {
  return http.post(`/projects/${projectId}/business-components/${componentId}/work-items/${objectType}/${objectId}/workflow-migrations`, payload)
}
