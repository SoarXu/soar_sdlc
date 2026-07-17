const NODE_WIDTH = 118
const NODE_HEIGHT = 42
const NODE_CENTER_X = NODE_WIDTH / 2
const NODE_CENTER_Y = NODE_HEIGHT / 2
const CORNER_RADIUS = 16
const PARALLEL_LANE_GAP = 28
const VERTICAL_LANE_GAP = 48
const BACKWARD_LANE_GAP = 36
const OBSTACLE_CLEARANCE = 21
const EDGE_LABEL_HALF_WIDTH = 40
const EDGE_LABEL_GAP = 8
const POSITION_EPSILON = 0.001
const POSITION_CLUSTER_ULP_MULTIPLIER = 8

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

  return edgeView(points, (start.x + end.x) / 2, (start.y + end.y) / 2)
}

export function buildWorkflowEdgeViews(states, transitions, transitionKey = defaultTransitionKey) {
  const resolved = resolveWorkflowEdges(states, transitions, transitionKey)
  const groupSizes = countEndpointGroups(resolved)
  const verticalGroups = clusterVerticalGroups(resolved)
  const groupIndexes = new Map()
  const verticalGroupIndexes = new Map()
  const verticalLabelReservations = new Map()
  const maximumNodeBottom = states.reduce((maximum, state) => (
    Math.max(maximum, state.y + NODE_HEIGHT)
  ), 0)
  const routingMetadata = new Map()
  let backwardLaneIndex = 0

  resolved.forEach((edge) => {
    const groupKey = endpointGroupKey(edge.transition)
    const groupIndex = groupIndexes.get(groupKey) || 0
    groupIndexes.set(groupKey, groupIndex + 1)
    const metadata = { groupKey, groupIndex }

    if (edge.transition.from_state_id !== edge.transition.to_state_id &&
      isVerticalConnection(edge.from, edge.to)) {
      const verticalGroupKey = verticalGroups.keys.get(edge)
      metadata.verticalGroupKey = verticalGroupKey
      metadata.verticalGroupIndex = verticalGroupIndexes.get(verticalGroupKey) || 0
      verticalGroupIndexes.set(verticalGroupKey, metadata.verticalGroupIndex + 1)
    } else if (edge.transition.from_state_id !== edge.transition.to_state_id &&
      centerOf(edge.to).x < centerOf(edge.from).x) {
      metadata.backwardLaneIndex = backwardLaneIndex
      backwardLaneIndex += 1
    }
    routingMetadata.set(edge, metadata)
  })

  const globalReservations = {
    labelRectangles: [],
    pathSegments: [],
    spatialIndex: createWorkflowReservationIndex()
  }
  const views = new Map()

  resolved
    .filter((edge) => edge.transition.from_state_id !== edge.transition.to_state_id)
    .forEach((edge) => {
      const metadata = routingMetadata.get(edge)
      let view

      if (metadata.verticalGroupKey !== undefined) {
        const verticalGroupKey = metadata.verticalGroupKey
        if (!verticalLabelReservations.has(verticalGroupKey)) {
          verticalLabelReservations.set(verticalGroupKey, { labelRectangles: [], pathSegments: [] })
        }
        view = buildVerticalView(
          edge.from,
          edge.to,
          states,
          metadata.verticalGroupIndex,
          verticalGroups.sizes.get(verticalGroupKey),
          verticalLabelReservations.get(verticalGroupKey)
        )
      } else if (metadata.backwardLaneIndex !== undefined) {
        view = buildBackwardView(
          edge.from,
          edge.to,
          states,
          maximumNodeBottom,
          metadata.backwardLaneIndex,
          globalReservations
        )
      } else {
        view = buildForwardView(
          edge.from,
          edge.to,
          states,
          metadata.groupIndex,
          groupSizes.get(metadata.groupKey),
          globalReservations
        )
      }

      views.set(edge, view)
      reserveEdgeViewGeometry(view, globalReservations)
    })

  globalReservations.outerBaseBounds = combinedRectangleBounds([
    ...states.map((state) => expandedRectangle(state, OBSTACLE_CLEARANCE)),
    ...globalReservations.labelRectangles,
    ...globalReservations.pathSegments.map((segment) => segmentBounds(segment.from, segment.to))
  ])
  globalReservations.selfLoopCount = 0

  resolved
    .filter((edge) => edge.transition.from_state_id === edge.transition.to_state_id)
    .forEach((edge) => {
      const metadata = routingMetadata.get(edge)
      views.set(edge, buildSelfLoopView(
        edge.from,
        states,
        metadata.groupIndex,
        groupSizes.get(metadata.groupKey),
        globalReservations
      ))
    })

  return resolvedEdgeViews(resolved, (edge) => views.get(edge))
}

export function buildWorkflowEdgePreviewViews(
  states,
  transitions,
  transitionKey = defaultTransitionKey
) {
  const resolved = resolveWorkflowEdges(states, transitions, transitionKey)
  return resolvedEdgeViews(resolved, (edge) => (
    edge.transition.from_state_id === edge.transition.to_state_id
      ? selfLoopCandidateView(rightSelfLoopCandidate(edge.from, PARALLEL_LANE_GAP))
      : buildWorkflowEdgeView(edge.from, edge.to)
  ))
}

function resolveWorkflowEdges(states, transitions, transitionKey) {
  const nodesById = new Map(states.map((state) => [state.id, state]))
  return transitions
    .map((transition, originalIndex) => ({
      transition,
      originalIndex,
      from: nodesById.get(transition.from_state_id),
      to: nodesById.get(transition.to_state_id),
      rawKey: transitionKey(transition)
    }))
    .filter(({ from, to }) => from && to)
    .sort(compareResolvedTransitions)
}

function resolvedEdgeViews(resolved, buildView) {
  const usedKeys = new Set()
  return resolved.map((edge) => {
    return {
      key: uniqueTransitionKey(edge, usedKeys),
      transition: edge.transition,
      ...buildView(edge)
    }
  })
}

function reserveEdgeViewGeometry(view, reservations) {
  reserveWorkflowLabelRectangle(reservations, edgeLabelRectangle(view))
  const points = Array.isArray(view.points) && view.points.length >= 2
    ? view.points
    : [view.start, view.end]
  reserveWorkflowPathSegments(
    reservations,
    roundedPolylineSegments(normalizeOrthogonalPoints(points))
  )
}

function buildVerticalView(from, to, states, laneIndex, laneCount, reservations) {
  const downward = centerOf(to).y > centerOf(from).y
  const start = anchorPoint(from, downward ? 'bottom' : 'top')
  const end = anchorPoint(to, downward ? 'top' : 'bottom')
  const obstacles = states.filter((state) => state !== from && state !== to)
  const labelBounds = states.map((state) => expandedRectangle(state, 0))
  const clearView = findVerticalRouteView(
    start,
    end,
    obstacles,
    laneIndex,
    laneCount,
    OBSTACLE_CLEARANCE,
    labelBounds,
    reservations
  )
  if (clearView) return reserveVerticalRoute(clearView, reservations)

  const nodeAvoidingView = findVerticalRouteView(
    start,
    end,
    obstacles,
    laneIndex,
    laneCount,
    0,
    labelBounds,
    reservations
  )
  if (nodeAvoidingView) {
    return {
      ...reserveVerticalRoute(nodeAvoidingView, reservations),
      degraded: true
    }
  }

  const centeredLaneIndex = laneIndex - (laneCount - 1) / 2
  const trackX = start.x + centeredLaneIndex * VERTICAL_LANE_GAP
  const direct = verticalRoutePoints(start, end, trackX)
  const labelAvoidingFallback = routeViewWithClearLabel(
    direct,
    labelBounds,
    reservations
  )
  if (labelAvoidingFallback) {
    return {
      ...reserveVerticalRoute(labelAvoidingFallback, reservations),
      degraded: true
    }
  }
  const fallbackView = degradedEdgeView(direct)
  reserveVerticalRouteGeometry(fallbackView, direct, reservations)
  return fallbackView
}

function findVerticalRouteView(
  start,
  end,
  obstacles,
  laneIndex,
  laneCount,
  clearance,
  labelBounds,
  reservations
) {
  const centeredLaneIndex = laneIndex - (laneCount - 1) / 2
  const trackX = start.x + centeredLaneIndex * VERTICAL_LANE_GAP
  const pathBounds = obstacles.map((state) => expandedRectangle(state, clearance))
  const verticalRoutePadding = Math.max(
    clearance + CORNER_RADIUS,
    EDGE_LABEL_HALF_WIDTH + EDGE_LABEL_GAP
  )
  const routingBounds = obstacles.map((state) => expandedRectangle(state, verticalRoutePadding))
  const candidates = [verticalRoutePoints(start, end, trackX)]

  if (routingBounds.length) {
    const laneOffset = laneIndex * VERTICAL_LANE_GAP
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
    candidates.push(...channels.map((channel) => verticalRoutePoints(start, end, channel)))
  }

  return firstClearRouteView(candidates, pathBounds, labelBounds, reservations)
}

function firstClearRouteView(candidates, pathBounds, labelBounds, reservations) {
  for (const candidate of candidates) {
    const points = normalizeOrthogonalPoints(candidate)
    if (!polylineClearsRectangles(points, pathBounds)) continue
    const view = routeViewWithClearLabel(points, labelBounds, reservations)
    if (view) return view
  }
  return null
}

function routeViewWithClearLabel(points, labelBounds, reservations) {
  const normalized = normalizeOrthogonalPoints(points)
  const pathSegments = roundedPolylineSegments(normalized)
  const pathLabelRectangles = reservationLabelsForSegments(reservations, pathSegments)
  if (segmentsIntersectRectangles(pathSegments, pathLabelRectangles)) return null
  const labelSearchLimit = labelBounds.length + reservations.labelRectangles.length +
    normalized.length + 4
  for (const label of labelPointsForPolyline(normalized, labelSearchLimit)) {
    const labelRectangle = edgeLabelRectangle(label)
    if (labelBounds.some((rectangle) => rectanglesIntersect(labelRectangle, rectangle))) continue
    if (reservationLabelsForRectangle(reservations, labelRectangle).some((rectangle) => (
      rectanglesIntersect(labelRectangle, rectangle)
    ))) continue
    if (segmentsIntersectRectangles(
      reservationPathsForRectangle(reservations, labelRectangle),
      [labelRectangle]
    )) continue
    return {
      view: edgeView(normalized, label.x, label.y),
      labelRectangle,
      pathSegments
    }
  }
  return null
}

function reservationLabelsForSegments(reservations, segments) {
  return reservations.spatialIndex
    ? queryWorkflowReservationsForSegments(
        reservations.spatialIndex,
        'labelRectangles',
        segments
      )
    : reservations.labelRectangles
}

function reservationLabelsForRectangle(reservations, rectangle) {
  return reservations.spatialIndex
    ? queryWorkflowReservations(reservations.spatialIndex, 'labelRectangles', rectangle)
    : reservations.labelRectangles
}

function reservationPathsForRectangle(reservations, rectangle) {
  return reservations.spatialIndex
    ? queryWorkflowReservations(reservations.spatialIndex, 'pathSegments', rectangle)
    : reservations.pathSegments
}

function leastCollidingRouteView(candidates, pathBounds, labelBounds, reservations) {
  let best = null

  candidates.forEach((candidate, candidateIndex) => {
    const points = normalizeOrthogonalPoints(candidate)
    if (points.length < 2) return
    const pathSegments = roundedPolylineSegments(points)
    const pathLabelRectangles = reservationLabelsForSegments(reservations, pathSegments)
    const labelSearchLimit = labelBounds.length + reservations.labelRectangles.length +
      points.length + 4
    const labels = labelPointsForPolyline(points, labelSearchLimit)
    if (!labels.length) labels.push(labelPointForPolyline(points))

    labels.forEach((label, labelIndex) => {
      const labelRectangle = edgeLabelRectangle(label)
      const score = pathBounds.filter((rectangle) => (
        segmentsIntersectRectangles(pathSegments, [rectangle])
      )).length + pathLabelRectangles.filter((rectangle) => (
        segmentsIntersectRectangles(pathSegments, [rectangle])
      )).length + labelBounds.filter((rectangle) => (
        rectanglesIntersect(labelRectangle, rectangle)
      )).length + reservationLabelsForRectangle(reservations, labelRectangle)
        .filter((rectangle) => rectanglesIntersect(labelRectangle, rectangle)).length +
        reservationPathsForRectangle(reservations, labelRectangle)
          .filter((segment) => segmentIntersectsRectangle(
            segment.from,
            segment.to,
            labelRectangle
          )).length

      if (!best || score < best.score) {
        best = { candidateIndex, labelIndex, label, points, score }
      }
    })
  })

  const fallback = best ?? {
    label: labelPointForPolyline(candidates[0]),
    points: normalizeOrthogonalPoints(candidates[0])
  }
  return {
    ...edgeView(fallback.points, fallback.label.x, fallback.label.y),
    degraded: true
  }
}

function reserveVerticalRoute(candidate, reservations) {
  reservations.labelRectangles.push(candidate.labelRectangle)
  reservations.pathSegments.push(...candidate.pathSegments)
  return candidate.view
}

function reserveVerticalRouteGeometry(view, points, reservations) {
  reservations.labelRectangles.push(edgeLabelRectangle(view))
  reservations.pathSegments.push(...roundedPolylineSegments(normalizeOrthogonalPoints(points)))
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

function buildForwardView(from, to, states, laneIndex, laneCount, reservations) {
  const start = anchorPoint(from, 'right')
  const end = anchorPoint(to, 'left')
  const obstacles = states.filter((state) => state !== from && state !== to)
  const labelBounds = states.map((state) => expandedRectangle(state, 0))
  const skippedNodes = states.filter((state) => (
    state !== from &&
    state !== to &&
    state.x < end.x &&
    state.x + NODE_WIDTH > start.x
  ))
  let trackY

  if (skippedNodes.length) {
    return buildObstacleAvoidingForwardView(
      start,
      end,
      obstacles,
      laneIndex,
      labelBounds,
      reservations
    )
  }

  const centeredLaneIndex = laneIndex - (laneCount - 1) / 2
  trackY = (start.y + end.y) / 2 + centeredLaneIndex * PARALLEL_LANE_GAP
  const stubLength = Math.max(12, Math.min(PARALLEL_LANE_GAP, (end.x - start.x) / 4))
  const startTrackX = start.x + stubLength
  const endTrackX = end.x - stubLength

  const direct = [
    start,
    { x: startTrackX, y: start.y },
    { x: startTrackX, y: trackY },
    { x: endTrackX, y: trackY },
    { x: endTrackX, y: end.y },
    end
  ]
  const clearView = firstClearRouteView(
    [direct],
    obstacles.map((state) => expandedRectangle(state, OBSTACLE_CLEARANCE)),
    labelBounds,
    reservations
  )
  if (clearView) return clearView.view

  const alternative = findForwardRouteView(
    start,
    end,
    obstacles,
    laneIndex,
    OBSTACLE_CLEARANCE,
    labelBounds,
    reservations
  )
  if (alternative) return alternative

  const nodeAvoiding = firstClearRouteView(
    [direct],
    obstacles.map((state) => expandedRectangle(state, 0)),
    labelBounds,
    reservations
  ) || findForwardRouteCandidate(
    start,
    end,
    obstacles,
    laneIndex,
    0,
    (points) => routeViewWithClearLabel(points, labelBounds, reservations)
  )
  if (nodeAvoiding) {
    return {
      ...(nodeAvoiding.view ?? nodeAvoiding),
      degraded: true
    }
  }

  const fallbackCandidates = [
    direct,
    ...collectForwardRouteCandidates(start, end, obstacles, laneIndex, 0)
  ]
  return leastCollidingRouteView(
    fallbackCandidates,
    obstacles.map((state) => expandedRectangle(state, 0)),
    labelBounds,
    reservations
  )
}

function buildObstacleAvoidingForwardView(
  start,
  end,
  obstacles,
  laneIndex,
  labelBounds,
  reservations
) {
  const clearView = findForwardRouteView(
    start,
    end,
    obstacles,
    laneIndex,
    OBSTACLE_CLEARANCE,
    labelBounds,
    reservations
  )
  if (clearView) return clearView

  const nodeAvoidingView = findForwardRouteView(
    start,
    end,
    obstacles,
    laneIndex,
    0,
    labelBounds,
    reservations
  )
  if (nodeAvoidingView) {
    return {
      ...nodeAvoidingView,
      degraded: true
    }
  }

  const laneOffset = laneIndex * PARALLEL_LANE_GAP
  const fallbackTrackY = Math.min(...obstacles.map((node) => node.y)) -
    OBSTACLE_CLEARANCE - CORNER_RADIUS - 1 - laneOffset
  const fallbackStartX = start.x + PARALLEL_LANE_GAP
  const fallbackEndX = end.x - PARALLEL_LANE_GAP
  return leastCollidingRouteView(
    [
      forwardRoutePoints(start, end, fallbackStartX, fallbackEndX, fallbackTrackY),
      ...collectForwardRouteCandidates(start, end, obstacles, laneIndex, 0)
    ],
    obstacles.map((state) => expandedRectangle(state, 0)),
    labelBounds,
    reservations
  )
}

function findForwardRouteView(
  start,
  end,
  obstacles,
  laneIndex,
  clearance,
  labelBounds,
  reservations
) {
  const candidate = findForwardRouteCandidate(
    start,
    end,
    obstacles,
    laneIndex,
    clearance,
    (points) => routeViewWithClearLabel(points, labelBounds, reservations)
  )
  return candidate?.view ?? null
}

function collectForwardRouteCandidates(start, end, obstacles, laneIndex, clearance) {
  const candidates = []
  findForwardRouteCandidate(
    start,
    end,
    obstacles,
    laneIndex,
    clearance,
    (points) => {
      candidates.push(points)
      return null
    }
  )
  return candidates
}

function findForwardRouteCandidate(
  start,
  end,
  obstacles,
  laneIndex,
  clearance,
  accept
) {
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
        const accepted = accept(points)
        if (accepted) return accepted
      }
    }
  }

  return null
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
  const segments = roundedPolylineSegments(points)
  const nearbyRectangles = filterRectanglesBySegmentBounds(segments, rectangles)
  for (const { from, to } of segments) {
    if (nearbyRectangles.some((rectangle) => segmentIntersectsRectangle(from, to, rectangle))) {
      return false
    }
  }
  return true
}

function segmentIntersectsRectangle(from, to, rectangle) {
  if (!segmentBoundsIntersectRectangle(from, to, rectangle)) return false
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

function segmentBoundsIntersectRectangle(from, to, rectangle) {
  return Math.max(from.x, to.x) >= rectangle.left &&
    Math.min(from.x, to.x) <= rectangle.right &&
    Math.max(from.y, to.y) >= rectangle.top &&
    Math.min(from.y, to.y) <= rectangle.bottom
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

export function createWorkflowReservationIndex(cellSize = 128) {
  if (!Number.isFinite(cellSize) || cellSize <= 0) {
    throw new RangeError('Workflow reservation cell size must be a positive finite number')
  }
  return {
    cellSize,
    buckets: {
      labelRectangles: new Map(),
      pathSegments: new Map()
    },
    boundsByType: {
      labelRectangles: new Map(),
      pathSegments: new Map()
    },
    orderByType: {
      labelRectangles: new Map(),
      pathSegments: new Map()
    },
    nextOrderByType: {
      labelRectangles: 0,
      pathSegments: 0
    }
  }
}

export function addWorkflowReservation(index, type, item) {
  const buckets = index.buckets[type]
  const boundsByItem = index.boundsByType[type]
  if (!buckets || boundsByItem.has(item)) return
  const bounds = type === 'pathSegments'
    ? segmentBounds(item.from, item.to)
    : item
  boundsByItem.set(item, bounds)
  index.orderByType[type].set(item, index.nextOrderByType[type])
  index.nextOrderByType[type] += 1
  forEachSpatialCell(bounds, index.cellSize, (key) => {
    if (!buckets.has(key)) buckets.set(key, [])
    buckets.get(key).push(item)
  })
}

export function queryWorkflowReservations(index, type, bounds) {
  const buckets = index.buckets[type]
  if (!buckets) return []
  const found = new Set()
  forEachSpatialCell(bounds, index.cellSize, (key) => {
    ;(buckets.get(key) || []).forEach((item) => found.add(item))
  })
  return [...found]
    .filter((item) => rectanglesIntersect(index.boundsByType[type].get(item), bounds))
    .sort((left, right) => (
      index.orderByType[type].get(left) - index.orderByType[type].get(right)
    ))
}

export function queryWorkflowReservationsForSegments(index, type, segments) {
  const buckets = index.buckets[type]
  if (!buckets) return []
  const segmentBoundsByCell = new Map()
  segments.forEach((segment) => {
    const bounds = segmentBounds(segment.from, segment.to)
    forEachSpatialCell(bounds, index.cellSize, (key) => {
      if (!segmentBoundsByCell.has(key)) segmentBoundsByCell.set(key, [])
      segmentBoundsByCell.get(key).push(bounds)
    })
  })
  const found = new Set()
  segmentBoundsByCell.forEach((boundsList, key) => {
    ;(buckets.get(key) || []).forEach((item) => {
      const itemBounds = index.boundsByType[type].get(item)
      if (boundsList.some((bounds) => rectanglesIntersect(itemBounds, bounds))) found.add(item)
    })
  })
  return [...found]
    .sort((left, right) => (
      index.orderByType[type].get(left) - index.orderByType[type].get(right)
    ))
}

function forEachSpatialCell(bounds, cellSize, visit) {
  const left = Math.floor(bounds.left / cellSize)
  const right = Math.floor(bounds.right / cellSize)
  const top = Math.floor(bounds.top / cellSize)
  const bottom = Math.floor(bounds.bottom / cellSize)
  for (let x = left; x <= right; x += 1) {
    for (let y = top; y <= bottom; y += 1) visit(`${x}:${y}`)
  }
}

function segmentBounds(from, to) {
  return {
    left: Math.min(from.x, to.x),
    top: Math.min(from.y, to.y),
    right: Math.max(from.x, to.x),
    bottom: Math.max(from.y, to.y)
  }
}

export function filterRectanglesBySegmentBounds(segments, rectangles) {
  if (!segments.length) return []
  const bounds = segments.reduce((combined, segment) => {
    const current = segmentBounds(segment.from, segment.to)
    return {
      left: Math.min(combined.left, current.left),
      top: Math.min(combined.top, current.top),
      right: Math.max(combined.right, current.right),
      bottom: Math.max(combined.bottom, current.bottom)
    }
  }, segmentBounds(segments[0].from, segments[0].to))
  return rectangles.filter((rectangle) => rectanglesIntersect(bounds, rectangle))
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

function buildBackwardView(from, to, states, maximumNodeBottom, laneIndex, reservations) {
  const start = anchorPoint(from, 'bottom')
  const end = anchorPoint(to, 'bottom')
  const trackY = Math.max(maximumNodeBottom, start.y, end.y) +
    (laneIndex + 1) * BACKWARD_LANE_GAP
  const rectangles = states
    .filter((state) => state !== from && state !== to)
    .map((state) => expandedRectangle(state, OBSTACLE_CLEARANCE))
  const nodeRectangles = states
    .filter((state) => state !== from && state !== to)
    .map((state) => expandedRectangle(state, 0))
  const labelBounds = states.map((state) => expandedRectangle(state, 0))
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
  const clearView = firstClearRouteView(candidates, rectangles, labelBounds, reservations)
  if (clearView) return clearView.view

  const nodeAvoidingView = firstClearRouteView(
    candidates,
    nodeRectangles,
    labelBounds,
    reservations
  )
  if (nodeAvoidingView) {
    return {
      ...nodeAvoidingView.view,
      degraded: true
    }
  }

  return leastCollidingRouteView(candidates, nodeRectangles, labelBounds, reservations)
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

function buildSelfLoopView(node, states, loopIndex, loopCount, reservations) {
  const obstacles = states.filter((state) => state !== node)
  const clearCandidate = findSelfLoopCandidate(
    node,
    obstacles,
    loopIndex,
    loopCount,
    OBSTACLE_CLEARANCE,
    reservations
  )
  if (clearCandidate) return reservedSelfLoopView(clearCandidate, reservations)

  const nodeAvoidingCandidate = findSelfLoopCandidate(
    node,
    obstacles,
    loopIndex,
    loopCount,
    0,
    reservations
  )
  if (nodeAvoidingCandidate) {
    return reservedSelfLoopView(nodeAvoidingCandidate, reservations, true)
  }

  const reservationOnlyCandidate = findSelfLoopCandidate(
    node,
    [],
    loopIndex,
    loopCount,
    0,
    reservations
  )
  if (reservationOnlyCandidate) {
    return reservedSelfLoopView(reservationOnlyCandidate, reservations, true)
  }

  const fallbackWithGeometry = leastCollidingOuterSelfLoopCandidate(
    node,
    obstacles,
    loopIndex,
    reservations
  )
  return reservedSelfLoopView(fallbackWithGeometry, reservations, true)
}

function findSelfLoopCandidate(node, obstacles, loopIndex, loopCount, clearance, reservations) {
  const pathRectangles = obstacles.map((state) => expandedRectangle(state, clearance))
  const nodeRectangles = obstacles.map((state) => expandedRectangle(state, 0))

  for (let expansion = 0; expansion < obstacles.length + 4; expansion += 1) {
    const distance = (loopIndex + 1 + expansion * loopCount) * PARALLEL_LANE_GAP
    const candidates = [
      rightSelfLoopCandidate(node, distance),
      bottomSelfLoopCandidate(node, distance),
      leftSelfLoopCandidate(node, distance),
      topSelfLoopCandidate(node, distance)
    ]

    for (const candidate of candidates) {
      const accepted = acceptedSelfLoopCandidate(
        candidate,
        pathRectangles,
        nodeRectangles,
        reservations
      )
      if (accepted) return accepted
    }
  }

  for (const candidate of outerSelfLoopCandidates(
    node,
    pathRectangles,
    reservations,
    (loopIndex + 1) * PARALLEL_LANE_GAP
  )) {
    const accepted = acceptedSelfLoopCandidate(
      candidate,
      pathRectangles,
      nodeRectangles,
      reservations
    )
    if (accepted) return accepted
  }

  return null
}

function acceptedSelfLoopCandidate(candidate, pathRectangles, nodeRectangles, reservations) {
  const points = normalizeOrthogonalPoints(candidate.points)
  if (!polylineClearsRectangles(points, pathRectangles)) return null
  if (!labelClearsRectangles(candidate, nodeRectangles)) return null
  const candidateWithGeometry = selfLoopCandidateGeometry({ ...candidate, points })
  return selfLoopClearsReservations(candidateWithGeometry, reservations)
    ? candidateWithGeometry
    : null
}

function outerSelfLoopCandidates(node, pathRectangles, reservations, minimumDistance) {
  const bounds = combinedRectangleBounds([
    ...(reservations.outerBaseBounds ? [reservations.outerBaseBounds] : []),
    ...pathRectangles,
  ])
  if (!bounds) {
    return [
      rightSelfLoopCandidate(node, minimumDistance),
      bottomSelfLoopCandidate(node, minimumDistance),
      leftSelfLoopCandidate(node, minimumDistance),
      topSelfLoopCandidate(node, minimumDistance)
    ]
  }
  const nodeRight = node.x + NODE_WIDTH
  const nodeBottom = node.y + NODE_HEIGHT
  const margin = CORNER_RADIUS + 1
  const outerLeft = Math.min(node.x - minimumDistance, bounds.left) - margin
  const outerTop = Math.min(node.y - minimumDistance, bounds.top) - margin
  const outerRight = Math.max(nodeRight + minimumDistance, bounds.right) + margin
  const outerBottom = Math.max(nodeBottom + minimumDistance, bounds.bottom) + margin
  const laneIndex = reservations.selfLoopCount || 0
  const verticalStep = 26 + EDGE_LABEL_GAP
  const horizontalStep = EDGE_LABEL_HALF_WIDTH * 2 + EDGE_LABEL_GAP
  const verticalSlots = Math.max(1, Math.floor((
    bounds.bottom - bounds.top - 2 * (13 + EDGE_LABEL_GAP)
  ) / verticalStep) + 1)
  const horizontalSlots = Math.max(1, Math.floor((
    bounds.right - bounds.left - 2 * (EDGE_LABEL_HALF_WIDTH + EDGE_LABEL_GAP)
  ) / horizontalStep) + 1)
  const sideCapacities = [verticalSlots, horizontalSlots, verticalSlots, horizontalSlots]
  const perimeterCapacity = sideCapacities.reduce((total, capacity) => total + capacity, 0)
  let perimeterLane = laneIndex % perimeterCapacity
  let firstDirection = 0
  while (perimeterLane >= sideCapacities[firstDirection]) {
    perimeterLane -= sideCapacities[firstDirection]
    firstDirection += 1
  }
  const verticalLane = firstDirection % 2 === 0
    ? perimeterLane
    : laneIndex % verticalSlots
  const horizontalLane = firstDirection % 2 === 1
    ? perimeterLane
    : laneIndex % horizontalSlots
  const verticalLabelY = bounds.top + 13 + EDGE_LABEL_GAP + verticalLane * verticalStep
  const horizontalLabelX = bounds.left + EDGE_LABEL_HALF_WIDTH + EDGE_LABEL_GAP +
    horizontalLane * horizontalStep
  const candidates = [
    rightWrappingSelfLoopCandidate(node, outerRight, outerTop, outerBottom, verticalLabelY),
    bottomWrappingSelfLoopCandidate(node, outerBottom, outerLeft, outerRight, horizontalLabelX),
    leftWrappingSelfLoopCandidate(node, outerLeft, outerTop, outerBottom, verticalLabelY),
    topWrappingSelfLoopCandidate(node, outerTop, outerLeft, outerRight, horizontalLabelX)
  ]
  return [...candidates.slice(firstDirection), ...candidates.slice(0, firstDirection)]
}

function combinedRectangleBounds(rectangles) {
  if (!rectangles.length) return null
  return rectangles.reduce((bounds, rectangle) => ({
    left: Math.min(bounds.left, rectangle.left),
    top: Math.min(bounds.top, rectangle.top),
    right: Math.max(bounds.right, rectangle.right),
    bottom: Math.max(bounds.bottom, rectangle.bottom)
  }), { ...rectangles[0] })
}

function leastCollidingOuterSelfLoopCandidate(node, obstacles, loopIndex, reservations) {
  const nodeRectangles = obstacles.map((state) => expandedRectangle(state, 0))
  const minimumDistance = (loopIndex + 1) * PARALLEL_LANE_GAP
  const candidates = outerSelfLoopCandidates(
    node,
    nodeRectangles,
    reservations,
    minimumDistance
  )
    .map((candidate) => {
      const points = normalizeOrthogonalPoints(candidate.points)
      return selfLoopCandidateGeometry({ ...candidate, points })
    })
    .filter((candidate) => labelClearsRectangles(candidate, nodeRectangles))
  const score = (candidate) => (
    nodeRectangles.filter((rectangle) => (
      segmentsIntersectRectangles(candidate.pathSegments, [rectangle])
    )).length +
    reservations.labelRectangles.filter((rectangle) => (
      rectanglesIntersect(candidate.labelRectangle, rectangle) ||
      segmentsIntersectRectangles(candidate.pathSegments, [rectangle])
    )).length +
    reservations.pathSegments.filter((segment) => (
      segmentIntersectsRectangle(segment.from, segment.to, candidate.labelRectangle)
    )).length
  )
  candidates.sort((left, right) => score(left) - score(right))
  if (candidates[0]) return candidates[0]

  const fallback = rightOuterSelfLoopCandidate(node, minimumDistance + PARALLEL_LANE_GAP)
  return selfLoopCandidateGeometry({
    ...fallback,
    points: normalizeOrthogonalPoints(fallback.points)
  })
}

function selfLoopCandidateGeometry(candidate) {
  return {
    ...candidate,
    labelRectangle: selfLoopLabelRectangle(candidate),
    pathSegments: roundedPolylineSegments(candidate.points)
  }
}

function selfLoopClearsReservations(candidate, reservations) {
  const labelRectangles = reservations.spatialIndex
    ? queryWorkflowReservations(
        reservations.spatialIndex,
        'labelRectangles',
        candidate.labelRectangle
      )
    : reservations.labelRectangles
  if (labelRectangles.some((rectangle) => (
    rectanglesIntersect(candidate.labelRectangle, rectangle)
  ))) return false
  const pathLabelRectangles = reservations.spatialIndex
    ? queryWorkflowReservationsForSegments(
        reservations.spatialIndex,
        'labelRectangles',
        candidate.pathSegments
      )
    : reservations.labelRectangles
  if (segmentsIntersectRectangles(candidate.pathSegments, pathLabelRectangles)) return false
  const pathSegments = reservations.spatialIndex
    ? queryWorkflowReservations(
        reservations.spatialIndex,
        'pathSegments',
        candidate.labelRectangle
      )
    : reservations.pathSegments
  return !segmentsIntersectRectangles(pathSegments, [candidate.labelRectangle])
}

function segmentsIntersectRectangles(segments, rectangles) {
  return segments.some(({ from, to }) => (
    rectangles.some((rectangle) => segmentIntersectsRectangle(from, to, rectangle))
  ))
}

function selfLoopLabelRectangle(candidate) {
  return {
    left: candidate.labelX - EDGE_LABEL_HALF_WIDTH,
    top: candidate.labelY - 13,
    right: candidate.labelX + EDGE_LABEL_HALF_WIDTH,
    bottom: candidate.labelY + 13
  }
}

function rightWrappingSelfLoopCandidate(node, outerX, outerTop, outerBottom, labelY) {
  const start = { x: node.x + NODE_WIDTH, y: node.y + NODE_HEIGHT / 3 }
  const end = { x: node.x + NODE_WIDTH, y: node.y + NODE_HEIGHT * 2 / 3 }
  const stubX = node.x + NODE_WIDTH + 1
  return {
    points: [
      start,
      { x: stubX, y: start.y },
      { x: stubX, y: outerTop },
      { x: outerX, y: outerTop },
      { x: outerX, y: outerBottom },
      { x: stubX, y: outerBottom },
      { x: stubX, y: end.y },
      end
    ],
    labelX: outerX + EDGE_LABEL_HALF_WIDTH + EDGE_LABEL_GAP,
    labelY
  }
}

function bottomWrappingSelfLoopCandidate(node, outerY, outerLeft, outerRight, labelX) {
  const start = { x: node.x + NODE_WIDTH * 2 / 3, y: node.y + NODE_HEIGHT }
  const end = { x: node.x + NODE_WIDTH / 3, y: node.y + NODE_HEIGHT }
  const stubY = node.y + NODE_HEIGHT + 1
  return {
    points: [
      start,
      { x: start.x, y: stubY },
      { x: outerRight, y: stubY },
      { x: outerRight, y: outerY },
      { x: outerLeft, y: outerY },
      { x: outerLeft, y: stubY },
      { x: end.x, y: stubY },
      end
    ],
    labelX,
    labelY: outerY + 13 + EDGE_LABEL_GAP
  }
}

function leftWrappingSelfLoopCandidate(node, outerX, outerTop, outerBottom, labelY) {
  const start = { x: node.x, y: node.y + NODE_HEIGHT * 2 / 3 }
  const end = { x: node.x, y: node.y + NODE_HEIGHT / 3 }
  const stubX = node.x - 1
  return {
    points: [
      start,
      { x: stubX, y: start.y },
      { x: stubX, y: outerBottom },
      { x: outerX, y: outerBottom },
      { x: outerX, y: outerTop },
      { x: stubX, y: outerTop },
      { x: stubX, y: end.y },
      end
    ],
    labelX: outerX - EDGE_LABEL_HALF_WIDTH - EDGE_LABEL_GAP,
    labelY
  }
}

function topWrappingSelfLoopCandidate(node, outerY, outerLeft, outerRight, labelX) {
  const start = { x: node.x + NODE_WIDTH / 3, y: node.y }
  const end = { x: node.x + NODE_WIDTH * 2 / 3, y: node.y }
  const stubY = node.y - 1
  return {
    points: [
      start,
      { x: start.x, y: stubY },
      { x: outerLeft, y: stubY },
      { x: outerLeft, y: outerY },
      { x: outerRight, y: outerY },
      { x: outerRight, y: stubY },
      { x: end.x, y: stubY },
      end
    ],
    labelX,
    labelY: outerY - 13 - EDGE_LABEL_GAP
  }
}

function rightOuterSelfLoopCandidate(node, distance) {
  const start = { x: node.x + NODE_WIDTH, y: node.y + NODE_HEIGHT / 3 }
  const end = { x: node.x + NODE_WIDTH, y: node.y + NODE_HEIGHT * 2 / 3 }
  const outerX = node.x + NODE_WIDTH + distance
  return {
    points: [start, { x: outerX, y: start.y }, { x: outerX, y: end.y }, end],
    labelX: outerX + EDGE_LABEL_HALF_WIDTH + EDGE_LABEL_GAP,
    labelY: (start.y + end.y) / 2
  }
}

function rightSelfLoopCandidate(node, distance) {
  const start = anchorPoint(node, 'right')
  const end = anchorPoint(node, 'bottom')
  const loopRight = node.x + NODE_WIDTH + distance
  const loopBottom = node.y + NODE_HEIGHT + distance

  return {
    points: [
      start,
      { x: loopRight, y: start.y },
      { x: loopRight, y: loopBottom },
      { x: end.x, y: loopBottom },
      end
    ],
    labelX: loopRight + EDGE_LABEL_HALF_WIDTH + EDGE_LABEL_GAP,
    labelY: (start.y + loopBottom) / 2
  }
}

function bottomSelfLoopCandidate(node, distance) {
  const start = anchorPoint(node, 'bottom')
  const end = anchorPoint(node, 'left')
  const loopBottom = node.y + NODE_HEIGHT + distance
  const loopLeft = node.x - distance

  return {
    points: [
      start,
      { x: start.x, y: loopBottom },
      { x: loopLeft, y: loopBottom },
      { x: loopLeft, y: end.y },
      end
    ],
    labelX: (start.x + loopLeft) / 2,
    labelY: loopBottom + 13 + EDGE_LABEL_GAP
  }
}

function leftSelfLoopCandidate(node, distance) {
  const start = anchorPoint(node, 'left')
  const end = anchorPoint(node, 'top')
  const loopLeft = node.x - distance
  const loopTop = node.y - distance

  return {
    points: [
      start,
      { x: loopLeft, y: start.y },
      { x: loopLeft, y: loopTop },
      { x: end.x, y: loopTop },
      end
    ],
    labelX: loopLeft - EDGE_LABEL_HALF_WIDTH - EDGE_LABEL_GAP,
    labelY: (start.y + loopTop) / 2
  }
}

function topSelfLoopCandidate(node, distance) {
  const start = anchorPoint(node, 'top')
  const end = anchorPoint(node, 'right')
  const loopTop = node.y - distance
  const loopRight = node.x + NODE_WIDTH + distance

  return {
    points: [
      start,
      { x: start.x, y: loopTop },
      { x: loopRight, y: loopTop },
      { x: loopRight, y: end.y },
      end
    ],
    labelX: (start.x + loopRight) / 2,
    labelY: loopTop - 13 - EDGE_LABEL_GAP
  }
}

function labelClearsRectangles(candidate, rectangles) {
  const labelRectangle = selfLoopLabelRectangle(candidate)
  return rectangles.every((rectangle) => !rectanglesIntersect(labelRectangle, rectangle))
}

function rectanglesIntersect(left, right) {
  return left.right >= right.left && left.left <= right.right &&
    left.bottom >= right.top && left.top <= right.bottom
}

function selfLoopCandidateView(candidate) {
  return edgeView(candidate.points, candidate.labelX, candidate.labelY)
}

function reservedSelfLoopView(candidate, reservations, degraded = false) {
  reserveWorkflowLabelRectangle(reservations, candidate.labelRectangle)
  reserveWorkflowPathSegments(reservations, candidate.pathSegments)
  if (Number.isFinite(reservations.selfLoopCount)) reservations.selfLoopCount += 1
  const view = selfLoopCandidateView(candidate)
  return degraded ? { ...view, degraded: true } : view
}

function reserveWorkflowLabelRectangle(reservations, rectangle) {
  reservations.labelRectangles.push(rectangle)
  if (reservations.spatialIndex) {
    addWorkflowReservation(reservations.spatialIndex, 'labelRectangles', rectangle)
  }
}

function reserveWorkflowPathSegments(reservations, segments) {
  reservations.pathSegments.push(...segments)
  if (reservations.spatialIndex) {
    segments.forEach((segment) => {
      addWorkflowReservation(reservations.spatialIndex, 'pathSegments', segment)
    })
  }
}

function edgeView(points, labelX, labelY) {
  return {
    path: roundedPolylinePath(points),
    points,
    labelX,
    labelY,
    start: points[0],
    end: points[points.length - 1],
    bounds: edgeViewBounds(points, labelX, labelY)
  }
}

function edgeViewBounds(points, labelX, labelY) {
  const labelRectangle = edgeLabelRectangle({ labelX, labelY })
  return points.reduce((bounds, point) => ({
    left: Math.min(bounds.left, point.x),
    top: Math.min(bounds.top, point.y),
    right: Math.max(bounds.right, point.x),
    bottom: Math.max(bounds.bottom, point.y)
  }), labelRectangle)
}

function routedEdgeView(points) {
  const normalized = normalizeOrthogonalPoints(points)
  const label = labelPointForPolyline(normalized)
  return edgeView(normalized, label.x, label.y)
}

function labelPointForPolyline(points) {
  return labelPointsForPolyline(points)[0] ?? {
    x: (points[0].x + points[points.length - 1].x) / 2,
    y: (points[0].y + points[points.length - 1].y) / 2
  }
}

function labelPointsForPolyline(points, maximumOffsetSteps = 0) {
  const segments = []

  for (let index = 1; index < points.length; index += 1) {
    const from = points[index - 1]
    const to = points[index]
    const horizontal = from.y === to.y
    const vertical = from.x === to.x
    const length = Math.hypot(to.x - from.x, to.y - from.y)
    if (!length || (!horizontal && !vertical)) continue
    segments.push({
      horizontal,
      index,
      length,
      from,
      to
    })
  }

  segments.sort((left, right) => (
    right.length - left.length ||
    Number(right.horizontal) - Number(left.horizontal) ||
    left.index - right.index
  ))
  const labels = []
  const used = new Set()
  segments.forEach((segment) => {
    const step = segment.horizontal
      ? EDGE_LABEL_HALF_WIDTH * 2 + EDGE_LABEL_GAP
      : 26 + EDGE_LABEL_GAP
    const maximumOffset = segment.length / 2
    const offsets = [0]
    const offsetSteps = Math.min(Math.floor(maximumOffset / step), maximumOffsetSteps)
    for (let stepIndex = 1; stepIndex <= offsetSteps; stepIndex += 1) {
      const offset = stepIndex * step
      offsets.push(-offset, offset)
    }
    offsets.forEach((offset) => {
      const label = segment.horizontal
        ? { x: (segment.from.x + segment.to.x) / 2 + offset, y: segment.from.y }
        : { x: segment.from.x, y: (segment.from.y + segment.to.y) / 2 + offset }
      const key = `${label.x}:${label.y}`
      if (used.has(key)) return
      used.add(key)
      labels.push(label)
    })
  })
  return labels
}

function edgeLabelRectangle(point) {
  const x = point.labelX ?? point.x
  const y = point.labelY ?? point.y
  return {
    left: x - EDGE_LABEL_HALF_WIDTH,
    top: y - 13,
    right: x + EDGE_LABEL_HALF_WIDTH,
    bottom: y + 13
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

function clusterVerticalGroups(edges) {
  const keys = new Map()
  const sizes = new Map()
  const verticalEdges = edges
    .filter((edge) => (
      edge.transition.from_state_id !== edge.transition.to_state_id &&
      isVerticalConnection(edge.from, edge.to)
    ))
    .map((edge) => ({ edge, centerX: verticalColumnCenterX(edge.from, edge.to) }))
    .sort((left, right) => (
      left.centerX - right.centerX || compareResolvedTransitions(left.edge, right.edge)
    ))
  let columnIndex = -1
  let clusterAnchorX

  verticalEdges.forEach(({ edge, centerX }) => {
    if (clusterAnchorX === undefined || exceedsPositionEpsilon(clusterAnchorX, centerX)) {
      columnIndex += 1
      clusterAnchorX = centerX
    }
    const key = `vertical-column-${columnIndex}`
    keys.set(edge, key)
    sizes.set(key, (sizes.get(key) || 0) + 1)
  })
  return { keys, sizes }
}

function exceedsPositionEpsilon(anchor, candidate) {
  const scale = Math.max(1, Math.abs(anchor), Math.abs(candidate))
  const floatingTolerance = Number.EPSILON * scale * POSITION_CLUSTER_ULP_MULTIPLIER
  return candidate - anchor > POSITION_EPSILON + floatingTolerance
}

function verticalColumnCenterX(from, to) {
  return (centerOf(from).x + centerOf(to).x) / 2
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
