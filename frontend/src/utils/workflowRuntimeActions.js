function priorityOf(action) {
  const value = action?.list_priority ?? action?.ui_config?.list_priority
  const priority = Number(value)
  return Number.isFinite(priority) ? priority : 100
}

function listDisplayOf(action) {
  return action?.list_display || action?.ui_config?.list_display || 'more'
}

function isDanger(action) {
  return (action?.button_type || action?.ui_config?.button_type) === 'danger'
}

function actionKeyOf(action) {
  return action?.action_key || ''
}

export async function replaceWorkflowTransitionMap(fetchBatch, projectIds = [], replaceMap = () => {}) {
  replaceMap({})
  const items = [...new Set(projectIds.filter((id) => id !== null && id !== undefined))]
    .map((id) => ({ object_type: 'project', id }))
  if (!items.length) return {}
  try {
    const { data } = await fetchBatch(items)
    const transitionMap = Object.fromEntries(
      (data.items || []).map((item) => [item.id, item.transitions || []])
    )
    replaceMap(transitionMap)
    return transitionMap
  } catch (error) {
    replaceMap({})
    throw error
  }
}

export function actionNeedsTargetStateSelection(action) {
  const routingMode = action?.routing_mode
  const allowedTargetStates = action?.allowed_target_states || []
  return ['manual_allowed', 'automatic_with_override'].includes(routingMode) && allowedTargetStates.length > 0
}

export function workflowCommandType(action) {
  return action?.ui_config?.command_type || ''
}

export function actionNeedsDialog(action) {
  return Boolean(
    action?.requires_form ||
      action?.confirm_required ||
      actionNeedsTargetStateSelection(action) ||
      action?.form_config?.allow_manual_owner ||
      (action?.form_config?.fields || []).length
  )
}

export function sortWorkflowActions(actions = []) {
  return [...actions].sort((a, b) => {
    const priorityDelta = priorityOf(a) - priorityOf(b)
    if (priorityDelta !== 0) return priorityDelta
    return actionKeyOf(a).localeCompare(actionKeyOf(b))
  })
}

export function visibleListActions(actions = []) {
  return sortWorkflowActions(actions).filter((action) => listDisplayOf(action) !== 'hidden')
}

export function visibleDetailActions(actions = []) {
  return sortWorkflowActions(actions).filter((action) => action?.ui_config?.visible_in_detail !== false)
}

export function splitListActions(actions = []) {
  const visibleActions = visibleListActions(actions).filter((action) => action?.ui_config?.visible_in_list !== false)
  if (!visibleActions.length) {
    return { primaryAction: null, moreActions: [] }
  }

  const explicitPrimary = visibleActions.filter((action) => listDisplayOf(action) === 'primary')
  const primaryAction = explicitPrimary[0] || visibleActions.find((action) => !isDanger(action)) || visibleActions[0]
  return {
    primaryAction,
    moreActions: visibleActions.filter((action) => action !== primaryAction)
  }
}
