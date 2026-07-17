import { layoutWorkflowNodes } from './workflowAutoLayout.js'

export async function requestWorkflowOrganization({
  states,
  transitions,
  initialStateId,
  confirm,
  notifyEmpty
}) {
  if (!states.length) {
    notifyEmpty()
    return { organized: false, states }
  }

  try {
    await confirm()
  } catch {
    return { organized: false, states }
  }

  return {
    organized: true,
    states: layoutWorkflowNodes(states, transitions, initialStateId)
  }
}
