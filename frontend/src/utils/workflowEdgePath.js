const NODE_WIDTH = 118
const NODE_HEIGHT = 42
const NODE_CENTER_X = NODE_WIDTH / 2
const NODE_CENTER_Y = NODE_HEIGHT / 2
const CORNER_RADIUS = 16
const PARALLEL_LANE_GAP = 28
const BACKWARD_LANE_GAP = 36
const OBSTACLE_CLEARANCE = 21
const EDGE_LABEL_HALF_WIDTH = 40
const EDGE_LABEL_GAP = 8
const POSITION_EPSILON = 0.001

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

  return resolved.map((edge) => {
    const groupKey = endpointGroupKey(edge.transition)
    const groupIndex = groupIndexes.get(groupKey) || 0
    groupIndexes.set(groupKey, groupIndex + 1)

    let view
    if (edge.transition.from_state_id === edge.transition.to_state_id) {
      view = buildSelfLoopView(edge.from, groupIndex)
    } else if (isVerticalConnection(edge.from, edge.to)) {
      view = buildVerticalView(
        edge.from,
        edge.to,
        states,
        groupIndex,
        groupSizes.get(groupKey)
      )
    } else if (centerOf(edge.to).x < centerOf(edge.from).x) {
      view = buildBackwardView(
        edge.from,
        edge.to,
        states,
        maximumNodeBottom,
        backwardLaneIndex
      )
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

function buildVerticalView(from, to, states, laneIndex, laneCount) {
  const downward = centerOf(to).y > centerOf(from).y
  const start = anchorPoint(from, downward ? 'bottom' : 'top')
  const end = anchorPoint(to, downward ? 'top' : 'bottom')
  const centeredLaneIndex = laneIndex - (laneCount - 1) / 2
  const trackX = start.x + centeredLaneIndex * PARALLEL_LANE_GAP
  const rectangles = states
    .filter((state) => state !== from && state !== to)
    .map((state) => expandedRectangle(state, OBSTACLE_CLEARANCE))
  const routingBounds = states
    .filter((state) => state !== from && state !== to)
    .map((state) => expandedRectangle(state, OBSTACLE_CLEARANCE + CORNER_RADIUS))
  const direct = verticalRoutePoints(start, end, trackX)
  const directPoints = firstClearPolyline([direct], rectangles)
  if (directPoints) return routedEdgeView(directPoints)

  const laneOffset = laneIndex * PARALLEL_LANE_GAP
  const leftChannel = Math.min(...routingBounds.map((rectangle) => rectangle.left)) -
    1 - laneOffset
  const rightChannel = Math.max(...routingBounds.map((rectangle) => rectangle.right)) +
    1 + laneOffset
  const channels = channelCandidates(
    trackX,
    [
      leftChannel,
      rightChannel,
      ...routingBounds.flatMap((rectangle) => (
        [rectangle.left - 1 - laneOffset, rectangle.right + 1 + laneOffset]
      ))
    ],
    () => true
  )
  const points = firstClearPolyline(
    channels.map((channel) => verticalRoutePoints(start, end, channel)),
    rectangles
  )

  if (!points) {
    return degradedEdgeView(direct)
  }
  return routedEdgeView(points)
}

function verticalRoutePoints(start, end, trackX) {
  if (trackX === start.x && start.x === end.x) return [start, end]
  return [
    start,
    { x: trackX, y: start.y },
    { x: trackX, y: end.y },
    end
  ]
}

function isVerticalConnection(from, to) {
  return Math.abs(centerOf(to).x - centerOf(from).x) <= POSITION_EPSILON
}

function buildForwardView(from, to, states, laneIndex, laneCount) {
  const start = anchorPoint(from, 'right')
  const end = anchorPoint(to, 'left')
  const obstacles = states.filter((state) => state !== from && state !== to)
  const skippedNodes = states.filter((state) => (
    state !== from &&
    state !== to &&
    state.x < end.x &&
    state.x + NODE_WIDTH > start.x
  ))
  let trackY

  if (skippedNodes.length) {
    return buildObstacleAvoidingForwardView(start, end, obstacles, laneIndex)
  }

  const centeredLaneIndex = laneIndex - (laneCount - 1) / 2
  trackY = (start.y + end.y) / 2 + centeredLaneIndex * PARALLEL_LANE_GAP
  const stubLength = Math.max(12, Math.min(PARALLEL_LANE_GAP, (end.x - start.x) / 4))
  const startTrackX = start.x + stubLength
  const endTrackX = end.x - stubLength

  return routedEdgeView([
    start,
    { x: startTrackX, y: start.y },
    { x: startTrackX, y: trackY },
    { x: endTrackX, y: trackY },
    { x: endTrackX, y: end.y },
    end
  ])
}

function buildObstacleAvoidingForwardView(start, end, obstacles, laneIndex) {
  const clearRoute = findForwardRoute(start, end, obstacles, laneIndex, OBSTACLE_CLEARANCE)
  if (clearRoute) return forwardRouteView(clearRoute)

  const nodeAvoidingRoute = findForwardRoute(start, end, obstacles, laneIndex, 0)
  if (nodeAvoidingRoute) {
    return {
      ...forwardRouteView(nodeAvoidingRoute),
      degraded: true
    }
  }

  const laneOffset = laneIndex * PARALLEL_LANE_GAP
  const fallbackTrackY = Math.min(...obstacles.map((node) => node.y)) -
    OBSTACLE_CLEARANCE - CORNER_RADIUS - 1 - laneOffset
  const fallbackStartX = start.x + PARALLEL_LANE_GAP
  const fallbackEndX = end.x - PARALLEL_LANE_GAP
  return degradedEdgeView(
    forwardRoutePoints(start, end, fallbackStartX, fallbackEndX, fallbackTrackY)
  )
}

function findForwardRoute(start, end, obstacles, laneIndex, clearance) {
  const routePadding = clearance + CORNER_RADIUS
  const rectangles = obstacles.map((node) => expandedRectangle(node, clearance))
  const routingBounds = obstacles.map((node) => expandedRectangle(node, routePadding))
  const above = Math.min(...routingBounds.map((rectangle) => rectangle.top)) - 1
  const below = Math.max(...routingBounds.map((rectangle) => rectangle.bottom)) + 1
  const leftOuter = Math.min(...routingBounds.map((rectangle) => rectangle.left)) - 1
  const rightOuter = Math.max(...routingBounds.map((rectangle) => rectangle.right)) + 1
  const internalBoundaries = routingBounds.flatMap((rectangle) => (
    [rectangle.left - 1, rectangle.right + 1]
  ))
  const startChannels = channelCandidates(
    start.x + PARALLEL_LANE_GAP,
    [start.x, leftOuter, rightOuter, ...internalBoundaries],
    (x) => x >= start.x && x < end.x
  )
  const endChannels = channelCandidates(
    end.x - PARALLEL_LANE_GAP,
    [end.x, leftOuter, rightOuter, ...internalBoundaries],
    (x) => x > start.x && x <= end.x
  )
  const laneOffset = laneIndex * PARALLEL_LANE_GAP
  const tracks = [above - laneOffset, below + laneOffset]
    .sort((left, right) => routeDistance(start, end, left) - routeDistance(start, end, right) || left - right)
  for (const trackY of tracks) {
    const safeStartChannels = startChannels
      .filter((trackX) => forwardLegClears(start, trackX, trackY, 1, rectangles))
    const safeEndChannels = endChannels
      .filter((trackX) => forwardLegClears(end, trackX, trackY, -1, rectangles))

    for (const startTrackX of safeStartChannels) {
      for (const endTrackX of safeEndChannels) {
        const points = firstClearPolyline([
          forwardRoutePoints(start, end, startTrackX, endTrackX, trackY)
        ], rectangles)
        if (!points) continue
        return {
          points,
          startTrackX,
          endTrackX,
          trackY
        }
      }
    }
  }

  return null
}

function forwardRouteView({ points }) {
  return routedEdgeView(points)
}

function forwardLegClears(anchor, trackX, trackY, direction, rectangles) {
  const trackExtension = trackX + direction * PARALLEL_LANE_GAP
  const points = direction > 0
    ? [
        anchor,
        { x: trackX, y: anchor.y },
        { x: trackX, y: trackY },
        { x: trackExtension, y: trackY }
      ]
    : [
        { x: trackExtension, y: trackY },
        { x: trackX, y: trackY },
        { x: trackX, y: anchor.y },
        anchor
      ]
  return polylineClearsRectangles(normalizeOrthogonalPoints(points), rectangles)
}

function forwardRoutePoints(start, end, startTrackX, endTrackX, trackY) {
  return [
    start,
    { x: startTrackX, y: start.y },
    { x: startTrackX, y: trackY },
    { x: endTrackX, y: trackY },
    { x: endTrackX, y: end.y },
    end
  ]
}

function channelCandidates(preferred, boundaries, allowed) {
  return [...new Set([preferred, ...boundaries].filter(allowed))]
    .sort((left, right) => Math.abs(left - preferred) - Math.abs(right - preferred) || left - right)
}

function expandedRectangle(node, padding) {
  return {
    left: node.x - padding,
    top: node.y - padding,
    right: node.x + NODE_WIDTH + padding,
    bottom: node.y + NODE_HEIGHT + padding
  }
}

function polylineClearsRectangles(points, rectangles) {
  for (const { from, to } of roundedPolylineSegments(points)) {
    if (rectangles.some((rectangle) => segmentIntersectsRectangle(from, to, rectangle))) {
      return false
    }
  }
  return true
}

function segmentIntersectsRectangle(from, to, rectangle) {
  let minimum = 0
  let maximum = 1
  const dx = to.x - from.x
  const dy = to.y - from.y
  const boundaries = [
    [-dx, from.x - rectangle.left],
    [dx, rectangle.right - from.x],
    [-dy, from.y - rectangle.top],
    [dy, rectangle.bottom - from.y]
  ]

  for (const [direction, distance] of boundaries) {
    if (direction === 0 && distance < 0) return false
    if (direction === 0) continue
    const ratio = distance / direction
    if (direction < 0) minimum = Math.max(minimum, ratio)
    else maximum = Math.min(maximum, ratio)
    if (minimum > maximum) return false
  }

  return true
}

function roundedPolylineSegments(points) {
  if (points.length < 2) return []
  const segments = []
  let cursor = points[0]

  for (let index = 1; index < points.length - 1; index += 1) {
    const previous = points[index - 1]
    const current = points[index]
    const next = points[index + 1]
    const before = pointToward(current, previous, CORNER_RADIUS)
    const after = pointToward(current, next, CORNER_RADIUS)
    segments.push({ from: cursor, to: before })

    let curveCursor = before
    for (let step = 1; step <= 16; step += 1) {
      const ratio = step / 16
      const curvePoint = quadraticPoint(before, current, after, ratio)
      segments.push({ from: curveCursor, to: curvePoint })
      curveCursor = curvePoint
    }
    cursor = after
  }

  segments.push({ from: cursor, to: points[points.length - 1] })
  return segments
}

function quadraticPoint(start, control, end, ratio) {
  const inverse = 1 - ratio
  return {
    x: inverse * inverse * start.x + 2 * inverse * ratio * control.x + ratio * ratio * end.x,
    y: inverse * inverse * start.y + 2 * inverse * ratio * control.y + ratio * ratio * end.y
  }
}

function normalizeOrthogonalPoints(points) {
  const normalized = []
  points.forEach((point) => {
    const previous = normalized[normalized.length - 1]
    if (!previous || previous.x !== point.x || previous.y !== point.y) normalized.push(point)
  })

  let index = 1
  while (index < normalized.length - 1) {
    const previous = normalized[index - 1]
    const current = normalized[index]
    const next = normalized[index + 1]
    if ((previous.x === current.x && current.x === next.x) ||
        (previous.y === current.y && current.y === next.y)) {
      normalized.splice(index, 1)
    } else {
      index += 1
    }
  }
  return normalized
}

function buildBackwardView(from, to, states, maximumNodeBottom, laneIndex) {
  const start = anchorPoint(from, 'bottom')
  const end = anchorPoint(to, 'bottom')
  const trackY = Math.max(maximumNodeBottom, start.y, end.y) +
    (laneIndex + 1) * BACKWARD_LANE_GAP
  const rectangles = states
    .filter((state) => state !== from && state !== to)
    .map((state) => expandedRectangle(state, OBSTACLE_CLEARANCE))
  const routingBounds = states
    .filter((state) => state !== from && state !== to)
    .map((state) => expandedRectangle(state, OBSTACLE_CLEARANCE + CORNER_RADIUS))
  const leftChannel = routingBounds.length
    ? Math.min(...routingBounds.map((rectangle) => rectangle.left)) - 1
    : Math.min(start.x, end.x) - PARALLEL_LANE_GAP
  const rightChannel = routingBounds.length
    ? Math.max(...routingBounds.map((rectangle) => rectangle.right)) + 1
    : Math.max(start.x, end.x) + PARALLEL_LANE_GAP
  const channels = [leftChannel, rightChannel]
    .sort((left, right) => (
      Math.abs(start.x - left) + Math.abs(end.x - left) -
      Math.abs(start.x - right) - Math.abs(end.x - right) || left - right
    ))
  const candidates = [
    backwardRoutePoints(start, end, start.x, end.x, trackY),
    ...channels.map((channel) => backwardRoutePoints(start, end, channel, end.x, trackY)),
    ...channels.map((channel) => backwardRoutePoints(start, end, start.x, channel, trackY)),
    backwardRoutePoints(start, end, channels[0], channels[1], trackY),
    backwardRoutePoints(start, end, channels[1], channels[0], trackY)
  ]
  const points = firstClearPolyline(candidates, rectangles)

  if (!points) {
    return degradedEdgeView(
      backwardRoutePoints(start, end, start.x, end.x, trackY)
    )
  }
  return routedEdgeView(points)
}

function backwardRoutePoints(start, end, startTrackX, endTrackX, trackY) {
  return [
    start,
    { x: startTrackX, y: start.y },
    { x: startTrackX, y: trackY },
    { x: endTrackX, y: trackY },
    { x: endTrackX, y: end.y },
    end
  ]
}

function firstClearPolyline(candidates, rectangles) {
  for (const candidate of candidates) {
    const points = normalizeOrthogonalPoints(candidate)
    if (polylineClearsRectangles(points, rectangles)) return points
  }
  return null
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
  ], loopRight + EDGE_LABEL_HALF_WIDTH + EDGE_LABEL_GAP, (start.y + loopBottom) / 2)
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

function routedEdgeView(points) {
  const normalized = normalizeOrthogonalPoints(points)
  const label = labelPointForPolyline(normalized)
  return edgeView(normalized, label.x, label.y)
}

function labelPointForPolyline(points) {
  let longestHorizontal
  let longestVertical

  for (let index = 1; index < points.length; index += 1) {
    const from = points[index - 1]
    const to = points[index]
    const horizontal = from.y === to.y
    const vertical = from.x === to.x
    const length = Math.hypot(to.x - from.x, to.y - from.y)
    if (!length || (!horizontal && !vertical)) continue
    const candidate = {
      length,
      point: { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 }
    }
    if (horizontal && (!longestHorizontal || length > longestHorizontal.length)) {
      longestHorizontal = candidate
    } else if (vertical && (!longestVertical || length > longestVertical.length)) {
      longestVertical = candidate
    }
  }

  return longestHorizontal?.point ?? longestVertical?.point ?? {
    x: (points[0].x + points[points.length - 1].x) / 2,
    y: (points[0].y + points[points.length - 1].y) / 2
  }
}

function degradedEdgeView(points) {
  return {
    ...routedEdgeView(points),
    degraded: true
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
