import { buildWorkflowEdgeViews } from './workflowEdgePath.js'
import {
  generatedDiagramConfigFromView,
  isManualDiagramRoute
} from './workflowManualRoute.js'

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
  const previewTransitions = transitions.map((transition) => (
    isManualDiagramRoute(transition.diagram_config)
      ? transition
      : { ...transition, diagram_config: null }
  ))
  return {
    states: previewStates,
    transitionViews: buildWorkflowEdgeViews(previewStates, previewTransitions, transitionKey)
  }
}

export function applyGeneratedRoutesFromViews(
  states,
  transitions,
  transitionViews,
  transitionKey
) {
  const statesById = new Map(states.map((state) => [state.id, state]))
  const viewsByKey = new Map(transitionViews.map((view) => [view.key, view]))

  return transitions.map((transition) => {
    if (isManualDiagramRoute(transition.diagram_config) ||
      transition.from_state_id === transition.to_state_id) {
      return transition
    }
    const from = statesById.get(transition.from_state_id)
    const to = statesById.get(transition.to_state_id)
    const view = viewsByKey.get(transitionKey(transition))
    if (!from || !to || !view) return transition
    return {
      ...transition,
      diagram_config: generatedDiagramConfigFromView(view, from, to)
    }
  })
}
