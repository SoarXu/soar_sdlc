function orderOf(action) {
  const order = Number(action?.sort_order)
  return Number.isFinite(order) ? order : 100
}

function listDisplayOf(action) {
  return action?.list_display || action?.ui_config?.list_display || 'more'
}

function transitionIdOf(action) {
  return Number(action?.transition_id) || 0
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
      actionNeedsTargetStateSelection(action) ||
      action?.form_config?.allow_manual_owner ||
      (action?.form_config?.fields || []).length
  )
}

export function actionNeedsConfirmation(action) {
  return Boolean(action?.confirm_required && !actionNeedsDialog(action))
}

export function workflowConfirmationMessage(action) {
  return `确认“${action?.action_name || '当前操作'}”吗？`
}

export function sortWorkflowActions(actions = []) {
  return [...actions].sort((a, b) => {
    const orderDelta = orderOf(a) - orderOf(b)
    if (orderDelta !== 0) return orderDelta
    return transitionIdOf(a) - transitionIdOf(b)
  })
}

export function visibleListActions(actions = []) {
  return sortWorkflowActions(actions)
}

export function visibleDetailActions(actions = []) {
  return sortWorkflowActions(actions)
}

export function splitListActions(actions = []) {
  const visibleActions = visibleListActions(actions)
  return {
    primaryActions: visibleActions.filter((action) => listDisplayOf(action) === 'primary'),
    moreActions: visibleActions.filter((action) => listDisplayOf(action) !== 'primary')
  }
}
