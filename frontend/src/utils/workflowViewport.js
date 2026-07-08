const NODE_WIDTH = 118
const NODE_HEIGHT = 42

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
  return {
    x: clamp(offset.x, viewport.width - canvas.width, viewport.width / 2),
    y: clamp(offset.y, viewport.height - canvas.height, viewport.height / 2)
  }
}

export function fitViewportToNodes(nodes, canvas, viewport) {
  if (!nodes.length) return { x: 0, y: 0 }

  const bounds = nodes.reduce(
    (result, node) => ({
      left: Math.min(result.left, node.x),
      top: Math.min(result.top, node.y),
      right: Math.max(result.right, node.x + NODE_WIDTH),
      bottom: Math.max(result.bottom, node.y + NODE_HEIGHT)
    }),
    { left: Infinity, top: Infinity, right: -Infinity, bottom: -Infinity }
  )
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
