const EDITABLE_WORK_ITEM_TYPES = new Set(['requirement', 'task', 'bug'])

export function resolveWorkbenchWorkflowCommand(item, commandType) {
  const objectId = Number(item?.id)
  if (commandType !== 'edit' || !EDITABLE_WORK_ITEM_TYPES.has(item?.object_type) || !Number.isInteger(objectId) || objectId <= 0) {
    return null
  }
  return {
    kind: 'edit',
    objectType: item.object_type,
    objectId
  }
}
