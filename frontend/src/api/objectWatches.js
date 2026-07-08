import { http } from './http'

export function fetchObjectWatch(objectType, objectId) {
  return http.get('/object-watches', { params: { object_type: objectType, object_id: objectId } })
}

export function watchObject(objectType, objectId) {
  return http.post('/object-watches', { object_type: objectType, object_id: objectId })
}

export function unwatchObject(objectType, objectId) {
  return http.delete('/object-watches', { params: { object_type: objectType, object_id: objectId } })
}
