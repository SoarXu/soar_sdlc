export function projectWorkflowCanvas(states, transitions) {
  const stateIds = new Set(states.map((state) => state.id))
  const activeStates = states.filter((state) => state.enabled !== false)
  const inactiveStates = states.filter((state) => state.enabled === false)
  const validTransitions = transitions
    .filter((transition) => (
      stateIds.has(transition.from_state_id) && stateIds.has(transition.to_state_id)
    ))
    .sort(compareTransitions)
  const routedTransitions = validTransitions.filter((transition) => (
    transition.from_state_id !== transition.to_state_id
  ))
  const stateActionsByStateId = new Map(states.map((state) => [state.id, []]))

  validTransitions
    .filter((transition) => transition.from_state_id === transition.to_state_id)
    .forEach((transition) => {
      stateActionsByStateId.get(transition.from_state_id).push(transition)
    })

  return {
    activeStates,
    inactiveStates,
    routedTransitions,
    stateActionsByStateId
  }
}

function compareTransitions(left, right) {
  const sortDifference = normalizedSortOrder(left.sort_order) - normalizedSortOrder(right.sort_order)
  return sortDifference || compareIds(left.id, right.id)
}

function normalizedSortOrder(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : 0
}

function compareIds(left, right) {
  const leftNumber = Number(left)
  const rightNumber = Number(right)
  if (Number.isFinite(leftNumber) && Number.isFinite(rightNumber) && leftNumber !== rightNumber) {
    return leftNumber - rightNumber
  }
  return String(left ?? '').localeCompare(String(right ?? ''))
}
