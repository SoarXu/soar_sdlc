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
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return { organized: false, states }
    }
    throw error
  }

  return {
    organized: true,
    states: layoutWorkflowNodes(states, transitions, initialStateId)
  }
}
