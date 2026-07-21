export const WORKFLOW_NODE_WIDTH = 118
export const WORKFLOW_NODE_HEIGHT = 42

const CORNER_GUARD = 8
const ENDPOINT_STUB = 28
const SIDES = new Set(['top', 'right', 'bottom', 'left'])
const STORED_ROUTING_MODES = new Set(['manual', 'generated'])

export function isManualDiagramRoute(config) {
  return config?.version === 1 && config?.routing_mode === 'manual'
}

export function isGeneratedDiagramRoute(config) {
  return config?.version === 1 && config?.routing_mode === 'generated'
}

export function anchorPointForNode(node, anchor) {
  if (!node || !SIDES.has(anchor?.side) || !Number.isFinite(Number(anchor?.ratio))) return null
  const ratio = clamp(Number(anchor.ratio), 0, 1)
  if (anchor.side === 'top' || anchor.side === 'bottom') {
    return {
      x: clamp(node.x + WORKFLOW_NODE_WIDTH * ratio, node.x + CORNER_GUARD, node.x + WORKFLOW_NODE_WIDTH - CORNER_GUARD),
      y: anchor.side === 'top' ? node.y : node.y + WORKFLOW_NODE_HEIGHT
    }
  }
  return {
    x: anchor.side === 'left' ? node.x : node.x + WORKFLOW_NODE_WIDTH,
    y: clamp(node.y + WORKFLOW_NODE_HEIGHT * ratio, node.y + CORNER_GUARD, node.y + WORKFLOW_NODE_HEIGHT - CORNER_GUARD)
  }
}

export function createManualDiagramConfig(view, from, to) {
  const points = normalizeManualWaypoints(view?.points || [view?.start, view?.end].filter(Boolean))
  if (points.length < 2) return null
  return {
    version: 1,
    routing_mode: 'manual',
    source_anchor: anchorForPoint(from, points[0]),
    target_anchor: anchorForPoint(to, points.at(-1)),
    waypoints: points.slice(1, -1).map(copyPoint)
  }
}

export function diagramRoutePoints(from, to, config) {
  if (!from || !to || config?.version !== 1 || !STORED_ROUTING_MODES.has(config?.routing_mode)) return null
  const start = anchorPointForNode(from, config.source_anchor)
  const end = anchorPointForNode(to, config.target_anchor)
  if (!start || !end) return null
  let waypoints = Array.isArray(config.waypoints)
    ? config.waypoints.filter(finitePoint).map(copyPoint)
    : []
  if (!waypoints.length) waypoints = defaultWaypoints(start, end, config.source_anchor.side)

  if (config.source_anchor.side === 'top' || config.source_anchor.side === 'bottom') {
    waypoints[0].x = start.x
  } else {
    waypoints[0].y = start.y
  }
  const last = waypoints.at(-1)
  if (config.target_anchor.side === 'top' || config.target_anchor.side === 'bottom') {
    last.x = end.x
  } else {
    last.y = end.y
  }

  const points = normalizeManualWaypoints([start, ...waypoints, end])
  return routeIsOrthogonal(points) ? points : null
}

export function manualRoutePoints(from, to, config) {
  return isManualDiagramRoute(config) ? diagramRoutePoints(from, to, config) : null
}

export function moveManualAnchor(config, endpoint, pointer, from, to) {
  if (!config || !['source', 'target'].includes(endpoint)) return null
  const node = endpoint === 'source' ? from : to
  const next = structuredClone(config)
  next[`${endpoint}_anchor`] = anchorForPoint(node, pointer)
  const start = anchorPointForNode(from, next.source_anchor)
  const end = anchorPointForNode(to, next.target_anchor)
  if (!start || !end) return null
  const current = manualRoutePoints(from, to, config)
  if (!current) return null

  if (endpoint === 'source') {
    const far = current.length > 2 ? current.at(-2) : end
    next.waypoints = endpointBridge(start, far, next.source_anchor.side, true)
  } else {
    const far = current.length > 2 ? current[1] : start
    next.waypoints = endpointBridge(end, far, next.target_anchor.side, false)
  }
  return configFromPoints(next, manualRoutePoints(from, to, next))
}

export function moveManualSegment(config, segmentIndex, pointer, from, to) {
  const points = manualRoutePoints(from, to, config)
  if (!points || segmentIndex <= 0 || segmentIndex >= points.length - 2) return null
  const start = points[segmentIndex]
  const end = points[segmentIndex + 1]
  if (start.y === end.y) {
    if (!Number.isFinite(pointer?.y)) return null
    start.y = pointer.y
    end.y = pointer.y
  } else if (start.x === end.x) {
    if (!Number.isFinite(pointer?.x)) return null
    start.x = pointer.x
    end.x = pointer.x
  } else {
    return null
  }
  return configFromPoints(config, normalizeManualWaypoints(points))
}

export function normalizeManualWaypoints(points) {
  const normalized = []
  for (const point of points || []) {
    if (!finitePoint(point)) continue
    const next = copyPoint(point)
    const previous = normalized.at(-1)
    if (previous && previous.x === next.x && previous.y === next.y) continue
    normalized.push(next)
    while (normalized.length >= 3) {
      const [a, b, c] = normalized.slice(-3)
      if ((a.x === b.x && b.x === c.x) || (a.y === b.y && b.y === c.y)) {
        normalized.splice(-2, 1)
      } else {
        break
      }
    }
  }
  return normalized
}

function anchorForPoint(node, point) {
  const distances = [
    { side: 'top', distance: Math.abs(point.y - node.y) },
    { side: 'right', distance: Math.abs(point.x - (node.x + WORKFLOW_NODE_WIDTH)) },
    { side: 'bottom', distance: Math.abs(point.y - (node.y + WORKFLOW_NODE_HEIGHT)) },
    { side: 'left', distance: Math.abs(point.x - node.x) }
  ]
  distances.sort((left, right) => left.distance - right.distance)
  const side = distances[0].side
  const ratio = side === 'top' || side === 'bottom'
    ? clamp((point.x - node.x) / WORKFLOW_NODE_WIDTH, 0, 1)
    : clamp((point.y - node.y) / WORKFLOW_NODE_HEIGHT, 0, 1)
  return { side, ratio }
}

function endpointBridge(endpoint, far, side, source) {
  const direction = side === 'top' || side === 'left' ? -1 : 1
  const stub = side === 'top' || side === 'bottom'
    ? { x: endpoint.x, y: endpoint.y + direction * ENDPOINT_STUB }
    : { x: endpoint.x + direction * ENDPOINT_STUB, y: endpoint.y }
  const corner = side === 'top' || side === 'bottom'
    ? { x: far.x, y: stub.y }
    : { x: stub.x, y: far.y }
  const route = source
    ? normalizeManualWaypoints([endpoint, stub, corner, far])
    : normalizeManualWaypoints([far, corner, stub, endpoint])
  return source ? route.slice(1) : route.slice(0, -1)
}

function defaultWaypoints(start, end, sourceSide) {
  if (start.x === end.x || start.y === end.y) return []
  return sourceSide === 'top' || sourceSide === 'bottom'
    ? [{ x: start.x, y: end.y }]
    : [{ x: end.x, y: start.y }]
}

function configFromPoints(config, points) {
  if (!points || points.length < 2) return null
  return {
    ...structuredClone(config),
    waypoints: points.slice(1, -1).map(copyPoint)
  }
}

function routeIsOrthogonal(points) {
  return points.length >= 2 && points.slice(1).every((point, index) => (
    point.x === points[index].x || point.y === points[index].y
  ))
}

function finitePoint(point) {
  return Number.isFinite(point?.x) && Number.isFinite(point?.y)
}

function copyPoint(point) {
  return { x: point.x, y: point.y }
}

function clamp(value, minimum, maximum) {
  return Math.max(minimum, Math.min(maximum, value))
}
