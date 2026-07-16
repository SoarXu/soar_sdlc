import { http } from './http'

export function fetchAssigneeRuleConfigs() {
  return http.get('/assignee-rule-configs')
}

export function fetchAssigneeRuleConfigTemplateSources() {
  return http.get('/assignee-rule-configs/template-sources')
}

export function fetchAssigneeRuleConfigProjectOptions() {
  return http.get('/assignee-rule-configs/project-options')
}

export function createAssigneeRuleConfig(payload) {
  return http.post('/assignee-rule-configs', payload)
}

export function updateAssigneeRuleConfig(id, payload) {
  return http.patch(`/assignee-rule-configs/${id}`, payload)
}

export function enableAssigneeRuleConfig(id) {
  return http.post(`/assignee-rule-configs/${id}/enable`)
}

export function disableAssigneeRuleConfig(id) {
  return http.post(`/assignee-rule-configs/${id}/disable`)
}
