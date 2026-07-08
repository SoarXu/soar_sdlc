const NODE_WIDTH = 118
const NODE_HEIGHT = 42
const NODE_CENTER_X = NODE_WIDTH / 2
const NODE_CENTER_Y = NODE_HEIGHT / 2
const CORNER_RADIUS = 16

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
