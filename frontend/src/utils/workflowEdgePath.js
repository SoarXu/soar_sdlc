const NODE_WIDTH = 118
const NODE_HEIGHT = 42
const NODE_CENTER_X = NODE_WIDTH / 2
const NODE_CENTER_Y = NODE_HEIGHT / 2
const CORNER_RADIUS = 16
const PARALLEL_LANE_GAP = 28
const BACKWARD_LANE_GAP = 36
const OBSTACLE_CLEARANCE = 21

export function buildWorkflowEdgeView(from, to) {
  const fromCenter = centerOf(from)
  const toCenter = centerOf(to)
  const dx = toCenter.x - fromCenter.x
  const dy = toCenter.y - fromCenter.y
  const vertical = Math.abs(dy) > Math.abs(dx) * 0.8
  const sourceSide = vertical ? (dy >= 0 ? 'bottom' : 'top') : (dx >= 0 ? 'right' : 'left')
  const targetSide = vertical ? (dy >= 0 ? 'top' : 'bottom') : (dx >= 0 ? 'left' : 'right')
  const start = anchorPoint(from, sourceSide)
  const end = anchorPoint(to, targetSide)
  const points = vertical ? verticalRoute(start, end) : horizontalRoute(start, end)

  return {
    path: roundedPolylinePath(points),
    labelX: (start.x + end.x) / 2,
    labelY: (start.y + end.y) / 2,
    start,
    end
  }
}

export function buildWorkflowEdgeViews(states, transitions, transitionKey = defaultTransitionKey) {
  const nodesById = new Map(states.map((state) => [state.id, state]))
  const resolved = transitions
    .map((transition, originalIndex) => ({
      transition,
      originalIndex,
      from: nodesById.get(transition.from_state_id),
      to: nodesById.get(transition.to_state_id),
      rawKey: transitionKey(transition)
    }))
    .filter(({ from, to }) => from && to)
    .sort(compareResolvedTransitions)
  const groupSizes = countEndpointGroups(resolved)
  const groupIndexes = new Map()
  const usedKeys = new Set()
  const maximumNodeBottom = states.reduce((maximum, state) => (
    Math.max(maximum, state.y + NODE_HEIGHT)
  ), 0)
  let backwardLaneIndex = 0
  let selfLoopIndex = 0

  return resolved.map((edge) => {
    const groupKey = endpointGroupKey(edge.transition)
    const groupIndex = groupIndexes.get(groupKey) || 0
    groupIndexes.set(groupKey, groupIndex + 1)

    let view
    if (edge.transition.from_state_id === edge.transition.to_state_id) {
      view = buildSelfLoopView(edge.from, selfLoopIndex)
      selfLoopIndex += 1
    } else if (centerOf(edge.to).x <= centerOf(edge.from).x) {
      view = buildBackwardView(edge.from, edge.to, maximumNodeBottom, backwardLaneIndex)
      backwardLaneIndex += 1
    } else {
      view = buildForwardView(
        edge.from,
        edge.to,
        states,
        groupIndex,
        groupSizes.get(groupKey)
      )
    }

    return {
      key: uniqueTransitionKey(edge, usedKeys),
      transition: edge.transition,
      ...view
    }
  })
}

function buildForwardView(from, to, states, laneIndex, laneCount) {
  const start = anchorPoint(from, 'right')
  const end = anchorPoint(to, 'left')
  const skippedNodes = states.filter((state) => (
    state !== from &&
    state !== to &&
    state.x < end.x &&
    state.x + NODE_WIDTH > start.x
  ))
  const stubLength = Math.max(12, Math.min(PARALLEL_LANE_GAP, (end.x - start.x) / 4))
  const startTrackX = start.x + stubLength
  const endTrackX = end.x - stubLength
  let trackY

  if (skippedNodes.length) {
    const above = Math.min(...skippedNodes.map((state) => state.y)) - OBSTACLE_CLEARANCE
    const below = Math.max(...skippedNodes.map((state) => state.y + NODE_HEIGHT)) + OBSTACLE_CLEARANCE
    const useAbove = routeDistance(start, end, above) <= routeDistance(start, end, below)
    trackY = useAbove
      ? above - laneIndex * PARALLEL_LANE_GAP
      : below + laneIndex * PARALLEL_LANE_GAP
  } else {
    const centeredLaneIndex = laneIndex - (laneCount - 1) / 2
    trackY = (start.y + end.y) / 2 + centeredLaneIndex * PARALLEL_LANE_GAP
  }

  return edgeView([
    start,
    { x: startTrackX, y: start.y },
    { x: startTrackX, y: trackY },
    { x: endTrackX, y: trackY },
    { x: endTrackX, y: end.y },
    end
  ], (startTrackX + endTrackX) / 2, trackY)
}

function buildBackwardView(from, to, maximumNodeBottom, laneIndex) {
  const start = anchorPoint(from, 'bottom')
  const end = anchorPoint(to, 'bottom')
  const trackY = Math.max(maximumNodeBottom, start.y, end.y) +
    (laneIndex + 1) * BACKWARD_LANE_GAP

  return edgeView([
    start,
    { x: start.x, y: trackY },
    { x: end.x, y: trackY },
    end
  ], (start.x + end.x) / 2, trackY)
}

function buildSelfLoopView(node, loopIndex) {
  const start = anchorPoint(node, 'right')
  const end = anchorPoint(node, 'bottom')
  const loopRight = node.x + NODE_WIDTH + (loopIndex + 1) * PARALLEL_LANE_GAP
  const loopBottom = node.y + NODE_HEIGHT + (loopIndex + 1) * BACKWARD_LANE_GAP

  return edgeView([
    start,
    { x: loopRight, y: start.y },
    { x: loopRight, y: loopBottom },
    { x: end.x, y: loopBottom },
    end
  ], loopRight, loopBottom)
}

function edgeView(points, labelX, labelY) {
  return {
    path: roundedPolylinePath(points),
    labelX,
    labelY,
    start: points[0],
    end: points[points.length - 1]
  }
}

function routeDistance(start, end, trackY) {
  return Math.abs(start.y - trackY) + Math.abs(end.y - trackY)
}

function countEndpointGroups(edges) {
  const sizes = new Map()
  edges.forEach(({ transition }) => {
    const key = endpointGroupKey(transition)
    sizes.set(key, (sizes.get(key) || 0) + 1)
  })
  return sizes
}

function endpointGroupKey(transition) {
  return `${typedId(transition.from_state_id)}>${typedId(transition.to_state_id)}`
}

function compareResolvedTransitions(left, right) {
  return compareIds(left.transition.from_state_id, right.transition.from_state_id) ||
    compareIds(left.transition.to_state_id, right.transition.to_state_id) ||
    normalizedSortOrder(left.transition.sort_order) - normalizedSortOrder(right.transition.sort_order) ||
    compareIds(left.rawKey, right.rawKey) ||
    left.originalIndex - right.originalIndex
}

function uniqueTransitionKey(edge, usedKeys) {
  const fallback = `${typedId(edge.transition.from_state_id)}>${typedId(edge.transition.to_state_id)}` +
    `:${normalizedSortOrder(edge.transition.sort_order)}:${edge.originalIndex}`
  const baseKey = edge.rawKey ?? fallback
  let key = baseKey
  let suffix = 2

  while (usedKeys.has(key)) {
    key = `${String(baseKey)}#${suffix}`
    suffix += 1
  }
  usedKeys.add(key)
  return key
}

function defaultTransitionKey(transition) {
  return transition.id ?? transition._client_id
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

  const typeDifference = typeof left < typeof right ? -1 : (typeof left > typeof right ? 1 : 0)
  return typeDifference || String(left).localeCompare(String(right))
}

function typedId(id) {
  return `${typeof id}:${String(id)}`
}

function centerOf(node) {
  return { x: node.x + NODE_CENTER_X, y: node.y + NODE_CENTER_Y }
}

function anchorPoint(node, side) {
  if (side === 'top') return { x: node.x + NODE_CENTER_X, y: node.y }
  if (side === 'bottom') return { x: node.x + NODE_CENTER_X, y: node.y + NODE_HEIGHT }
  if (side === 'left') return { x: node.x, y: node.y + NODE_CENTER_Y }
  return { x: node.x + NODE_WIDTH, y: node.y + NODE_CENTER_Y }
}

function horizontalRoute(start, end) {
  const midX = (start.x + end.x) / 2
  return [
    start,
    { x: midX, y: start.y },
    { x: midX, y: end.y },
    end
  ]
}

function verticalRoute(start, end) {
  const midY = (start.y + end.y) / 2
  return [
    start,
    { x: start.x, y: midY },
    { x: end.x, y: midY },
    end
  ]
}

function roundedPolylinePath(points) {
  if (points.length < 2) return ''
  const commands = [`M ${formatPoint(points[0])}`]

  for (let index = 1; index < points.length - 1; index += 1) {
    const previous = points[index - 1]
    const current = points[index]
    const next = points[index + 1]
    const before = pointToward(current, previous, CORNER_RADIUS)
    const after = pointToward(current, next, CORNER_RADIUS)
    commands.push(`L ${formatPoint(before)}`)
    commands.push(`Q ${formatPoint(current)} ${formatPoint(after)}`)
  }

  commands.push(`L ${formatPoint(points[points.length - 1])}`)
  return commands.join(' ')
}

function pointToward(from, to, distance) {
  const dx = to.x - from.x
  const dy = to.y - from.y
  const length = Math.hypot(dx, dy)
  if (!length) return from
  const offset = Math.min(distance, length / 2)
  return {
    x: from.x + (dx / length) * offset,
    y: from.y + (dy / length) * offset
  }
}

function formatPoint(point) {
  return `${round(point.x)} ${round(point.y)}`
}

function round(value) {
  return Math.round(value * 100) / 100
}
