export function workflowGraphSnapshot({
  definitionId,
  objectType,
  initialStateId,
  states,
  transitions
}) {
  return JSON.stringify(stableValue({
    definitionId: definitionId ?? null,
    objectType: objectType ?? null,
    initialStateId: initialStateId ?? null,
    states: states || [],
    transitions: transitions || []
  }))
}

function stableValue(value) {
  if (Array.isArray(value)) return value.map(stableValue)
  if (!value || typeof value !== 'object') return value

  return Object.keys(value).sort().reduce((result, key) => {
    const item = value[key]
    if (item !== undefined && typeof item !== 'function' && typeof item !== 'symbol') {
      result[key] = stableValue(item)
    }
    return result
  }, {})
}

