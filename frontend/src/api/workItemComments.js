import { http } from './http'

export function fetchWorkItemComments(objectType, objectId) {
  return http.get('/work-item-comments', { params: { object_type: objectType, object_id: objectId } })
}

export function createWorkItemComment(payload) {
  return http.post('/work-item-comments', payload)
}
