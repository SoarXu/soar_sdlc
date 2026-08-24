export function setWorkflowStateEnabled(states, transitions, stateId, enabled) {
  const nextStates = states.map((state) => (
    state.id === stateId ? { ...state, enabled } : { ...state }
  ))
  const enabledByStateId = new Map(nextStates.map((state) => [state.id, state.enabled]))
  const nextTransitions = transitions.map((transition) => {
    const endpointsEnabled = (
      enabledByStateId.get(transition.from_state_id)
      && enabledByStateId.get(transition.to_state_id)
    )
    if (!endpointsEnabled) {
      return {
        ...transition,
        enabled: false,
        auto_disabled_by_state: Boolean(transition.auto_disabled_by_state || transition.enabled)
      }
    }
    if (transition.auto_disabled_by_state) {
      return { ...transition, enabled: true, auto_disabled_by_state: false }
    }
    return { ...transition }
  })
  return { states: nextStates, transitions: nextTransitions }
}
