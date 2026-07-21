import { buildWorkflowEdgeViews } from './workflowEdgePath.js'

export function createWorkflowDragFrame(
  states,
  transitions,
  stateId,
  position,
  transitionKey
) {
  if (!Array.isArray(states) || !Array.isArray(transitions) ||
    !Number.isFinite(position?.x) || !Number.isFinite(position?.y)) {
    return null
  }
  const index = states.findIndex((state) => state.id === stateId)
  if (index < 0) return null

  const previewStates = states.map((state, stateIndex) => (
    stateIndex === index
      ? { ...state, x: position.x, y: position.y }
      : state
  ))
  return {
    states: previewStates,
    transitionViews: buildWorkflowEdgeViews(previewStates, transitions, transitionKey)
  }
}
