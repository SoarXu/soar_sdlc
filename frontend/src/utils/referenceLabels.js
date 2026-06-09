export function labelById(items, id, key = 'name') {
  if (!id) return '-'
  const item = items.find((entry) => entry.id === id)
  return item ? item[key] || item.full_name || item.username || `#${id}` : `#${id}`
}

export function userLabel(users, id) {
  return labelById(users, id, 'full_name')
}

export function idOptionsFromCsv(value) {
  return value
    .split(',')
    .map((item) => Number(item.trim()))
    .filter(Boolean)
}
