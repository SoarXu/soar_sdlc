import { layoutWorkflowWithElk } from './workflowElkLayout.js'

export async function requestWorkflowOrganization({
  states,
  transitions,
  initialStateId,
  confirm,
  notifyEmpty,
  layout = layoutWorkflowWithElk
}) {
  if (!states.length) {
    notifyEmpty()
    return { organized: false, states, transitions }
  }

  try {
    await confirm()
  } catch (error) {
    if (error === 'cancel' || error === 'close') {
      return { organized: false, states, transitions }
    }
    throw error
  }

  const organized = await layout(states, transitions, initialStateId)
  return { organized: true, ...organized }
}
