export function toWorkItemPatchPayload(source = {}) {
  const { owner_id: _ownerId, status: _status, ...payload } = source
  return payload
}
