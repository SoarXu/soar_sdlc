import { WORKFLOW_LAYOUT } from './workflowAutoLayout.js'
import { WORKFLOW_NODE_HEIGHT, WORKFLOW_NODE_WIDTH } from './workflowManualRoute.js'

const EDGE_LABEL_WIDTH = 80
const EDGE_LABEL_HEIGHT = 26
const MAX_WAYPOINTS = 32
const DEFAULT_TIMEOUT_MS = 15000
const DISABLED_COLUMNS = 4

const ELK_LAYOUT_OPTIONS = Object.freeze({
  'elk.algorithm': 'layered',
  'elk.direction': 'RIGHT',
  'elk.edgeRouting': 'ORTHOGONAL',
  'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
  'elk.layered.crossingMinimization.greedySwitch.type': 'TWO_SIDED',
  'elk.layered.nodePlacement.strategy': 'BRANDES_KOEPF',
  'elk.layered.nodePlacement.bk.edgeStraightening': 'IMPROVE_STRAIGHTNESS',
  'elk.layered.spacing.nodeNodeBetweenLayers': '180',
  'elk.spacing.nodeNode': '80',
  'elk.spacing.edgeNode': '24',
  'elk.spacing.edgeEdge': '16',
  'elk.padding': '[top=80,left=80,bottom=80,right=80]'
})

let layoutRequestId = 0
let workerRequestId = 0
let elkWorker = null
const workerRequests = new Map()

export function createWorkflowElkGraph(states, transitions, initialStateId) {
  const activeStates = states.filter((state) => state.enabled !== false)
  const activeIds = new Set(activeStates.map((state) => state.id))
  const childrenById = new Map(activeStates.map((state) => {
    const id = elkNodeId(state.id)
    return [state.id, {
      id,
      width: WORKFLOW_NODE_WIDTH,
      height: WORKFLOW_NODE_HEIGHT,
      ports: [],
      layoutOptions: {
        'elk.portConstraints': 'FIXED_ORDER',
        ...(state.id === initialStateId
          ? { 'elk.layered.layering.layerConstraint': 'FIRST' }
          : {})
      }
    }]
  }))

  const edges = []
  transitions.forEach((transition, index) => {
    const fromId = transition.from_state_id
    const toId = transition.to_state_id
    if (fromId === toId || !activeIds.has(fromId) || !activeIds.has(toId)) return

    const sourceNode = childrenById.get(fromId)
    const targetNode = childrenById.get(toId)
    const sourcePortId = `${sourceNode.id}/port/out/${index}`
    const targetPortId = `${targetNode.id}/port/in/${index}`
    sourceNode.ports.push(elkPort(sourcePortId, 'EAST'))
    targetNode.ports.push(elkPort(targetPortId, 'WEST'))
    edges.push({
      id: elkEdgeId(index),
      sources: [sourcePortId],
      targets: [targetPortId],
      labels: [{
        id: `${elkEdgeId(index)}/label`,
        text: String(transition.action_name ?? ''),
        width: EDGE_LABEL_WIDTH,
        height: EDGE_LABEL_HEIGHT
      }]
    })
  })

  return {
    id: 'workflow-root',
    layoutOptions: { ...ELK_LAYOUT_OPTIONS },
    children: activeStates.map((state) => childrenById.get(state.id)),
    edges
  }
}

export function convertWorkflowElkResult(result, states, transitions) {
  if (!result || !Array.isArray(result.children) || !Array.isArray(result.edges)) {
    throw new Error('Invalid ELK layout result')
  }

  const resultNodes = new Map(result.children.map((node) => [node.id, node]))
  const activeStates = states.filter((state) => state.enabled !== false)
  const activeIds = new Set(activeStates.map((state) => state.id))
  const positionedActiveStates = activeStates.map((state) => {
    const node = resultNodes.get(elkNodeId(state.id))
    if (!node || !finiteNumber(node.x) || !finiteNumber(node.y)) {
      throw new Error('Invalid ELK layout result')
    }
    return { ...structuredClone(state), x: node.x, y: node.y }
  })
  const positionedById = new Map(positionedActiveStates.map((state) => [state.id, state]))
  const activeBottom = positionedActiveStates.length
    ? Math.max(...positionedActiveStates.map((state) => state.y + WORKFLOW_NODE_HEIGHT))
    : WORKFLOW_LAYOUT.marginY - WORKFLOW_LAYOUT.disabledRegionGap
  const disabledTop = activeBottom + WORKFLOW_LAYOUT.disabledRegionGap
  let disabledIndex = 0

  const convertedStates = states.map((state) => {
    if (state.enabled !== false) return positionedById.get(state.id)
    const row = Math.floor(disabledIndex / DISABLED_COLUMNS)
    const column = disabledIndex % DISABLED_COLUMNS
    disabledIndex += 1
    return {
      ...structuredClone(state),
      x: WORKFLOW_LAYOUT.marginX + column * WORKFLOW_LAYOUT.layerGap,
      y: disabledTop + row * (WORKFLOW_NODE_HEIGHT + WORKFLOW_LAYOUT.rowClearance)
    }
  })
  const convertedById = new Map(convertedStates.map((state) => [state.id, state]))
  const resultEdges = new Map(result.edges.map((edge) => [edge.id, edge]))

  const convertedTransitions = transitions.map((transition, index) => {
    const clone = structuredClone(transition)
    clone.diagram_config = null
    if (
      transition.from_state_id === transition.to_state_id ||
      !activeIds.has(transition.from_state_id) ||
      !activeIds.has(transition.to_state_id)
    ) {
      return clone
    }

    const edge = resultEdges.get(elkEdgeId(index))
    clone.diagram_config = generatedConfigFromEdge(
      edge,
      convertedById.get(transition.from_state_id),
      convertedById.get(transition.to_state_id)
    )
    return clone
  })

  return { states: convertedStates, transitions: convertedTransitions }
}

export async function layoutWorkflowWithElk(
  states,
  transitions,
  initialStateId,
  options = {}
) {
  const requestId = ++layoutRequestId
  const graph = createWorkflowElkGraph(states, transitions, initialStateId)
  const layout = options.layout || layoutInWorker
  const timeoutMs = finiteNumber(options.timeoutMs) ? options.timeoutMs : DEFAULT_TIMEOUT_MS
  const result = await withTimeout(Promise.resolve().then(() => layout(graph)), timeoutMs)
  if (requestId !== layoutRequestId) throw new Error('Stale ELK layout result')
  return convertWorkflowElkResult(result, states, transitions)
}

function generatedConfigFromEdge(edge, from, to) {
  if (!edge || !Array.isArray(edge.sections) || edge.sections.length !== 1) return null
  const section = edge.sections[0]
  const points = normalizeOrthogonalPoints([
    section.startPoint,
    ...(Array.isArray(section.bendPoints) ? section.bendPoints : []),
    section.endPoint
  ])
  if (points.length < 2 || points.length - 2 > MAX_WAYPOINTS) return null
  if (!routeIsOrthogonal(points)) return null

  const sourceAnchor = anchorForBoundaryPoint(from, points[0])
  const targetAnchor = anchorForBoundaryPoint(to, points.at(-1))
  if (!sourceAnchor || !targetAnchor) return null

  return {
    version: 1,
    routing_mode: 'generated',
    source_anchor: sourceAnchor,
    target_anchor: targetAnchor,
    waypoints: points.slice(1, -1)
  }
}

function normalizeOrthogonalPoints(points) {
  const normalized = []
  for (const point of points) {
    if (!finitePoint(point)) return []
    const next = { x: point.x, y: point.y }
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

function anchorForBoundaryPoint(node, point) {
  if (!node || !finitePoint(point)) return null
  const boundaries = [
    { side: 'top', distance: Math.abs(point.y - node.y) },
    { side: 'right', distance: Math.abs(point.x - (node.x + WORKFLOW_NODE_WIDTH)) },
    { side: 'bottom', distance: Math.abs(point.y - (node.y + WORKFLOW_NODE_HEIGHT)) },
    { side: 'left', distance: Math.abs(point.x - node.x) }
  ].sort((left, right) => left.distance - right.distance)
  if (boundaries[0].distance > 0.001) return null
  const side = boundaries[0].side
  const ratio = side === 'top' || side === 'bottom'
    ? (point.x - node.x) / WORKFLOW_NODE_WIDTH
    : (point.y - node.y) / WORKFLOW_NODE_HEIGHT
  if (!finiteNumber(ratio) || ratio < 0 || ratio > 1) return null
  return { side, ratio }
}

function routeIsOrthogonal(points) {
  return points.slice(1).every((point, index) => (
    point.x === points[index].x || point.y === points[index].y
  ))
}

function elkPort(id, side) {
  return {
    id,
    width: 0,
    height: 0,
    layoutOptions: { 'elk.port.side': side }
  }
}

function elkNodeId(id) {
  return `node/${typeof id}/${encodeURIComponent(String(id))}`
}

function elkEdgeId(index) {
  return `edge/${index}`
}

function layoutInWorker(graph) {
  const worker = getElkWorker()
  const requestId = ++workerRequestId
  return new Promise((resolve, reject) => {
    workerRequests.set(requestId, { resolve, reject })
    worker.postMessage({ requestId, graph })
  })
}

function getElkWorker() {
  if (elkWorker) return elkWorker
  if (typeof Worker === 'undefined') throw new Error('ELK worker is unavailable')
  elkWorker = new Worker(new URL('../workers/workflowElk.worker.js', import.meta.url), {
    type: 'module'
  })
  elkWorker.onmessage = ({ data }) => {
    const pending = workerRequests.get(data?.requestId)
    if (!pending) return
    workerRequests.delete(data.requestId)
    if (data.error) pending.reject(new Error(data.error))
    else pending.resolve(data.result)
  }
  elkWorker.onerror = (event) => {
    const error = new Error(event?.message || 'ELK worker failed')
    workerRequests.forEach(({ reject }) => reject(error))
    workerRequests.clear()
    elkWorker?.terminate()
    elkWorker = null
  }
  return elkWorker
}

function withTimeout(promise, timeoutMs) {
  let timer
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error('ELK layout timed out')), timeoutMs)
  })
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer))
}

function finitePoint(point) {
  return finiteNumber(point?.x) && finiteNumber(point?.y)
}

function finiteNumber(value) {
  return Number.isFinite(value)
}
