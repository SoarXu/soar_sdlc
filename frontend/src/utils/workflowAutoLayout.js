export const WORKFLOW_LAYOUT = Object.freeze({
  marginX: 80,
  marginY: 80,
  layerGap: 240,
  rowGap: 120,
  nodeHeight: 42,
  actionHeight: 24,
  actionGap: 6,
  actionTopGap: 8,
  rowClearance: 24,
  disabledRegionGap: 120
})

export function layoutWorkflowNodes(states, transitions, initialStateId) {
  if (!states.length) return []

  const nodesById = new Map(states.map((state) => [state.id, state]))
  const nodeIds = [...nodesById.keys()].sort((leftId, rightId) => (
    compareStates(nodesById.get(leftId), nodesById.get(rightId))
  ))
  const outgoing = new Map(nodeIds.map((id) => [id, []]))
  const incoming = new Map(nodeIds.map((id) => [id, []]))

  const selfActionCount = new Map(nodeIds.map((id) => [id, 0]))
  for (const transition of transitions) {
    const fromId = transition.from_state_id
    const toId = transition.to_state_id
    if (!nodesById.has(fromId) || !nodesById.has(toId)) continue
    if (fromId === toId) {
      selfActionCount.set(fromId, selfActionCount.get(fromId) + 1)
      continue
    }
    outgoing.get(fromId).push(toId)
    incoming.get(toId).push(fromId)
  }

  for (const ids of [...outgoing.values(), ...incoming.values()]) {
    ids.sort((leftId, rightId) => compareStates(nodesById.get(leftId), nodesById.get(rightId)))
  }

  const activeIds = new Set(nodeIds.filter((id) => nodesById.get(id).enabled !== false))
  const inactiveIds = nodeIds.filter((id) => !activeIds.has(id))
  const activeNodeIds = nodeIds.filter((id) => activeIds.has(id))
  const zeroIndegreeIds = activeNodeIds.filter((id) => (
    incoming.get(id).every((sourceId) => !activeIds.has(sourceId))
  ))
  const effectiveInitialId = activeIds.has(initialStateId)
    ? initialStateId
    : (zeroIndegreeIds[0] ?? activeNodeIds[0])
  const rootOrder = uniqueIds([
    effectiveInitialId,
    ...zeroIndegreeIds,
    ...activeNodeIds
  ]).filter((id) => id != null)

  const mainIds = effectiveInitialId == null
    ? new Set()
    : collectWeakComponent(effectiveInitialId, outgoing, incoming, new Set(), activeIds)
  const regions = mainIds.size
    ? [{ ids: mainIds, preferredRootId: effectiveInitialId }]
    : []
  const assigned = new Set(mainIds)

  for (const rootId of rootOrder) {
    if (assigned.has(rootId)) continue
    const regionIds = collectWeakComponent(rootId, outgoing, incoming, assigned, activeIds)
    if (!regionIds.size) continue
    regionIds.forEach((id) => assigned.add(id))
    regions.push({ ids: regionIds, preferredRootId: rootId })
  }

  const coordinates = new Map()
  let regionTop = WORKFLOW_LAYOUT.marginY

  for (const region of regions) {
    const layers = buildRegionLayers(
      region.ids,
      region.preferredRootId,
      outgoing,
      incoming,
      nodesById
    )
    const layerMetrics = layers.map(([layer, ids]) => ({
      layer,
      ids,
      offsets: rowOffsets(ids, selfActionCount),
      height: layerHeight(ids, selfActionCount)
    }))
    const maximumHeight = Math.max(1, ...layerMetrics.map(({ height }) => height))

    for (const { layer, ids, offsets, height } of layerMetrics) {
      const layerOffset = (maximumHeight - height) / 2
      ids.forEach((id, row) => {
        coordinates.set(id, {
          x: WORKFLOW_LAYOUT.marginX + layer * WORKFLOW_LAYOUT.layerGap,
          y: regionTop + layerOffset + offsets[row]
        })
      })
    }

    regionTop += maximumHeight + WORKFLOW_LAYOUT.rowGap
  }

  const activeBottom = activeNodeIds.length
    ? Math.max(...activeNodeIds.map((id) => (
        coordinates.get(id).y + nodeBlockHeight(id, selfActionCount)
      )))
    : WORKFLOW_LAYOUT.marginY - WORKFLOW_LAYOUT.disabledRegionGap
  let disabledTop = activeBottom + WORKFLOW_LAYOUT.disabledRegionGap
  const disabledColumns = 4
  for (let index = 0; index < inactiveIds.length; index += disabledColumns) {
    const rowIds = inactiveIds.slice(index, index + disabledColumns)
    rowIds.forEach((id, column) => {
      coordinates.set(id, {
        x: WORKFLOW_LAYOUT.marginX + column * WORKFLOW_LAYOUT.layerGap,
        y: disabledTop
      })
    })
    disabledTop += Math.max(...rowIds.map((id) => nodeBlockHeight(id, selfActionCount))) +
      WORKFLOW_LAYOUT.rowClearance
  }

  return states.map((state) => ({
    ...state,
    ...coordinates.get(state.id)
  }))
}

function buildRegionLayers(regionIds, preferredRootId, outgoing, incoming, nodesById) {
  const regionSet = new Set(regionIds)
  const sortedIds = [...regionIds].sort((leftId, rightId) => (
    compareStates(nodesById.get(leftId), nodesById.get(rightId))
  ))
  const zeroIndegreeIds = sortedIds.filter((id) => (
    incoming.get(id).every((sourceId) => !regionSet.has(sourceId))
  ))
  const roots = uniqueIds([preferredRootId, ...zeroIndegreeIds, ...sortedIds])
    .filter((id) => regionSet.has(id))
  const keptOutgoing = new Map(sortedIds.map((id) => [id, []]))
  const visitState = new Map()

  const visit = (sourceId) => {
    visitState.set(sourceId, 'visiting')
    for (const targetId of outgoing.get(sourceId)) {
      if (!regionSet.has(targetId) || visitState.get(targetId) === 'visiting') continue
      keptOutgoing.get(sourceId).push(targetId)
      if (!visitState.has(targetId)) visit(targetId)
    }
    visitState.set(sourceId, 'visited')
  }

  roots.forEach((id) => {
    if (!visitState.has(id)) visit(id)
  })

  const keptIndegree = new Map(sortedIds.map((id) => [id, 0]))
  for (const targetIds of keptOutgoing.values()) {
    targetIds.forEach((id) => keptIndegree.set(id, keptIndegree.get(id) + 1))
  }

  const ready = sortedIds.filter((id) => keptIndegree.get(id) === 0)
  const levelById = new Map(sortedIds.map((id) => [id, 0]))

  while (ready.length) {
    ready.sort((leftId, rightId) => compareStates(nodesById.get(leftId), nodesById.get(rightId)))
    const sourceId = ready.shift()
    for (const targetId of keptOutgoing.get(sourceId)) {
      levelById.set(targetId, Math.max(levelById.get(targetId), levelById.get(sourceId) + 1))
      keptIndegree.set(targetId, keptIndegree.get(targetId) - 1)
      if (keptIndegree.get(targetId) === 0) ready.push(targetId)
    }
  }

  const secondaryRoots = sortedIds.filter((id) => (
    id !== preferredRootId &&
    [...keptOutgoing.values()].every((targetIds) => !targetIds.includes(id))
  ))
  secondaryRoots.forEach((rootId) => {
    const targetLevels = keptOutgoing.get(rootId)
      .map((targetId) => levelById.get(targetId))
      .filter((level) => Number.isFinite(level) && level > 0)
    if (targetLevels.length) {
      levelById.set(rootId, Math.max(0, Math.min(...targetLevels) - 1))
    }
  })
  for (let pass = 0; pass < sortedIds.length; pass += 1) {
    let changed = false
    for (const [sourceId, targetIds] of keptOutgoing) {
      for (const targetId of targetIds) {
        const nextLevel = levelById.get(sourceId) + 1
        if (nextLevel > levelById.get(targetId)) {
          levelById.set(targetId, nextLevel)
          changed = true
        }
      }
    }
    if (!changed) break
  }

  const layersByIndex = new Map()
  for (const id of sortedIds) {
    const layer = levelById.get(id)
    if (!layersByIndex.has(layer)) layersByIndex.set(layer, [])
    layersByIndex.get(layer).push(id)
  }

  return [...layersByIndex.entries()].sort(([left], [right]) => left - right)
}

function collectWeakComponent(rootId, outgoing, incoming, excluded, allowed = null) {
  const visited = new Set()
  const pending = [rootId]

  while (pending.length) {
    const id = pending.pop()
    if (visited.has(id) || excluded.has(id) || (allowed && !allowed.has(id))) continue
    visited.add(id)
    outgoing.get(id).forEach((neighborId) => {
      if (!allowed || allowed.has(neighborId)) pending.push(neighborId)
    })
    incoming.get(id).forEach((neighborId) => {
      if (!allowed || allowed.has(neighborId)) pending.push(neighborId)
    })
  }

  return visited
}

function rowOffsets(ids, selfActionCount) {
  const offsets = []
  let offset = 0
  ids.forEach((id) => {
    offsets.push(offset)
    offset += Math.max(
      WORKFLOW_LAYOUT.rowGap,
      nodeBlockHeight(id, selfActionCount) + WORKFLOW_LAYOUT.rowClearance
    )
  })
  return offsets
}

function layerHeight(ids, selfActionCount) {
  if (!ids.length) return 0
  const offsets = rowOffsets(ids, selfActionCount)
  const lastId = ids[ids.length - 1]
  return offsets[offsets.length - 1] + nodeBlockHeight(lastId, selfActionCount)
}

function nodeBlockHeight(id, selfActionCount) {
  const hasActions = (selfActionCount.get(id) || 0) > 0
  if (!hasActions) return WORKFLOW_LAYOUT.nodeHeight
  return WORKFLOW_LAYOUT.nodeHeight + WORKFLOW_LAYOUT.actionTopGap +
    WORKFLOW_LAYOUT.actionHeight + WORKFLOW_LAYOUT.actionGap
}

function compareStates(left, right) {
  const sortOrderDifference = normalizedSortOrder(left.sort_order) - normalizedSortOrder(right.sort_order)
  return sortOrderDifference || compareIds(left.id, right.id)
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

function uniqueIds(ids) {
  return [...new Set(ids)]
}
