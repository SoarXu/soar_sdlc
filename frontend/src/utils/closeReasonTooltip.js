export async function loadCloseReasonMap(items, fetchStatusOperations) {
  const closedItems = items.filter((item) => item.status === 'closed')
  const entries = await Promise.all(
    closedItems.map(async (item) => {
      try {
        const { data } = await fetchStatusOperations(item.id)
        const closeOperation = [...data].reverse().find((operation) => operation.action === 'close')
        return [item.id, closeOperation ? closeReasonText(closeOperation) : '']
      } catch {
        return [item.id, '']
      }
    })
  )
  return Object.fromEntries(entries.filter(([, text]) => Boolean(text)))
}

export function closeReasonText(operation) {
  const parts = []
  if (operation.reason) parts.push(operation.reason)
  if (operation.remark) parts.push(operation.remark)
  return parts.map(escapeHtml).join('<br>')
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}
