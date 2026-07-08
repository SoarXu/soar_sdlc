import { http } from './http'

export function fetchAssigneeRuleConfigs() {
  return http.get('/assignee-rule-configs')
}

export function createAssigneeRuleConfig(payload) {
  return http.post('/assignee-rule-configs', payload)
}

export function updateAssigneeRuleConfig(id, payload) {
  return http.patch(`/assignee-rule-configs/${id}`, payload)
}

export function deleteAssigneeRuleConfig(id) {
  return http.delete(`/assignee-rule-configs/${id}`)
}
