export function batchAssignmentTransition(row) {
  return (row?.transitions || []).find((transition) => transition?.bulk_assignment?.supported) || null
}

export function canSelectForBatchAssignment(row, selectedRows = []) {
  const transition = batchAssignmentTransition(row)
  if (!transition) return false
  const selectedObjectType = selectedRows[0]?.object_type
  if (selectedObjectType && row.object_type && row.object_type !== selectedObjectType) return false
  const selectedProjectId = selectedRows[0]?.project_id
  return selectedProjectId === undefined || selectedProjectId === null || row.project_id === selectedProjectId
}

export function eligibleAssigneeIds(rows = []) {
  if (!rows.length) return []
  const firstIds = batchAssignmentTransition(rows[0])?.bulk_assignment?.eligible_assignee_ids || []
  return firstIds.filter((userId) => rows.every((row) => (
    batchAssignmentTransition(row)?.bulk_assignment?.eligible_assignee_ids?.includes(userId)
  )))
}

export function isBatchAssignmentReasonRequired(rows = []) {
  return rows.some((row) => batchAssignmentTransition(row)?.bulk_assignment?.requires_delegate_reason)
}

export function toBatchAssignmentItems(rows = []) {
  return rows.map((row) => ({ id: row.id, transition_id: batchAssignmentTransition(row)?.transition_id }))
}
