function groupOf(transition) {
  return transition?.ui_config?.list_display === 'primary' ? 'primary' : 'more'
}

function identityOf(transition) {
  return transition?.id ?? transition?._client_id
}

function byOrder(a, b) {
  const orderDelta = (Number(a.sort_order) || 100) - (Number(b.sort_order) || 100)
  if (orderDelta !== 0) return orderDelta
  return String(identityOf(a)).localeCompare(String(identityOf(b)))
}

export function groupStateTransitions(transitions = [], stateId) {
  const outgoing = transitions.filter((item) => item.enabled && item.from_state_id === stateId)
  return {
    primary: outgoing.filter((item) => groupOf(item) === 'primary').sort(byOrder),
    more: outgoing.filter((item) => groupOf(item) === 'more').sort(byOrder)
  }
}

export function nextGroupSortOrder(transitions = [], stateId, group) {
  const grouped = groupStateTransitions(transitions, stateId)
  const items = grouped[group === 'primary' ? 'primary' : 'more']
  return items.length ? Math.max(...items.map((item) => Number(item.sort_order) || 0)) + 10 : 10
}

export function moveStateTransition(transitions = [], transitionIdentity, targetGroup, targetIndex) {
  const selected = transitions.find((item) => identityOf(item) === transitionIdentity)
  if (!selected?.enabled) return transitions
  const stateId = selected.from_state_id
  const normalizedGroup = targetGroup === 'primary' ? 'primary' : 'more'
  const grouped = groupStateTransitions(transitions, stateId)
  const primary = grouped.primary.filter((item) => identityOf(item) !== transitionIdentity)
  const more = grouped.more.filter((item) => identityOf(item) !== transitionIdentity)
  const target = normalizedGroup === 'primary' ? primary : more
  const index = Math.max(0, Math.min(Number(targetIndex) || 0, target.length))
  target.splice(index, 0, selected)

  const updates = new Map()
  for (const [group, items] of [['primary', primary], ['more', more]]) {
    items.forEach((item, itemIndex) => {
      updates.set(identityOf(item), {
        ...item,
        sort_order: (itemIndex + 1) * 10,
        ui_config: { ...(item.ui_config || {}), list_display: group }
      })
    })
  }
  return transitions.map((item) => updates.get(identityOf(item)) || item)
}
