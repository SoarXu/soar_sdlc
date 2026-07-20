const NODE_WIDTH = 118
const NODE_HEIGHT = 42

export function workflowCanvasSize(
  nodes,
  minimumCanvas = { width: 2400, height: 1400 },
  padding = { left: 160, top: 120, right: 160, bottom: 120 },
  edgeViews = []
) {
  const nodeBounds = nodes.map((node) => ({
    left: node.x,
    top: node.y,
    right: node.x + NODE_WIDTH,
    bottom: node.y + NODE_HEIGHT
  }))
  const contentBounds = [...nodeBounds, ...edgeViews.map((edge) => edge.bounds)]
    .reduce((bounds, item) => ({
      left: Math.min(bounds.left, item.left),
      top: Math.min(bounds.top, item.top),
      right: Math.max(bounds.right, item.right),
      bottom: Math.max(bounds.bottom, item.bottom)
    }), { left: Infinity, top: Infinity, right: 0, bottom: 0 })
  const left = contentBounds.left < 0
    ? contentBounds.left - (padding.left ?? 0)
    : 0
  const top = contentBounds.top < 0
    ? contentBounds.top - (padding.top ?? 0)
    : 0
  const right = Math.max(minimumCanvas.width, contentBounds.right + padding.right)
  const bottom = Math.max(minimumCanvas.height, contentBounds.bottom + padding.bottom)

  return {
    left,
    top,
    right,
    bottom,
    width: right - left,
    height: bottom - top
  }
}

export function applyPanDelta(offset, delta, canvas, viewport) {
  return clampViewport(
    {
      x: offset.x + delta.dx,
      y: offset.y + delta.dy
    },
    canvas,
    viewport
  )
}

export function clampViewport(offset, canvas, viewport) {
  const left = canvas.left ?? 0
  const top = canvas.top ?? 0
  const right = canvas.right ?? left + canvas.width
  const bottom = canvas.bottom ?? top + canvas.height

  return {
    x: clamp(offset.x, viewport.width - right, viewport.width / 2 - left),
    y: clamp(offset.y, viewport.height - bottom, viewport.height / 2 - top)
  }
}

export function fitViewportToNodes(nodes, canvas, viewport, edgeViews = []) {
  if (!nodes.length && !edgeViews.length) return { x: 0, y: 0 }

  const nodeBounds = nodes.map((node) => ({
    left: node.x,
    top: node.y,
    right: node.x + NODE_WIDTH,
    bottom: node.y + NODE_HEIGHT
  }))
  const bounds = [...nodeBounds, ...edgeViews.map((edge) => edge.bounds)]
    .reduce((result, item) => ({
      left: Math.min(result.left, item.left),
      top: Math.min(result.top, item.top),
      right: Math.max(result.right, item.right),
      bottom: Math.max(result.bottom, item.bottom)
    }), { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity })
  const contentCenter = {
    x: (bounds.left + bounds.right) / 2,
    y: (bounds.top + bounds.bottom) / 2
  }
  const nextOffset = {
    x: viewport.width / 2 - contentCenter.x,
    y: viewport.height / 2 - contentCenter.y
  }

  return clampViewport(nextOffset, canvas, viewport)
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value))
}
