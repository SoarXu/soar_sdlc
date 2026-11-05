function deletionDepth(row, byId, visited = new Set()) {
  if (!row.parent_task_id || visited.has(row.id)) return 0
  const parent = byId.get(row.parent_task_id)
  if (!parent) return 0
  visited.add(row.id)
  return 1 + deletionDepth(parent, byId, visited)
}

export async function deleteSelectedRows(rows, deleteRow) {
  const byId = new Map(rows.map((row) => [row.id, row]))
  const ordered = [...rows].sort((a, b) => deletionDepth(b, byId) - deletionDepth(a, byId))
  const deleted = []
  const failed = []
  for (const row of ordered) {
    try {
      await deleteRow(row.id)
      deleted.push(row)
    } catch (error) {
      failed.push({ row, error })
    }
  }
  return { deleted, failed }
}
