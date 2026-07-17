export const WORKFLOW_LAYOUT = Object.freeze({
  marginX: 80,
  marginY: 80,
  layerGap: 240,
  rowGap: 120
})

export function layoutWorkflowNodes(states, transitions, initialStateId) {
  if (!states.length) return []

  const nodesById = new Map(states.map((state) => [state.id, state]))
  const nodeIds = [...nodesById.keys()].sort((leftId, rightId) => (
    compareStates(nodesById.get(leftId), nodesById.get(rightId))
  ))
  const outgoing = new Map(nodeIds.map((id) => [id, []]))
  const incoming = new Map(nodeIds.map((id) => [id, []]))

  for (const transition of transitions) {
    const fromId = transition.from_state_id
    const toId = transition.to_state_id
    if (!nodesById.has(fromId) || !nodesById.has(toId)) continue
    outgoing.get(fromId).push(toId)
    incoming.get(toId).push(fromId)
  }

  for (const ids of [...outgoing.values(), ...incoming.values()]) {
    ids.sort((leftId, rightId) => compareStates(nodesById.get(leftId), nodesById.get(rightId)))
  }

  const zeroIndegreeIds = nodeIds.filter((id) => incoming.get(id).length === 0)
  const effectiveInitialId = nodesById.has(initialStateId)
    ? initialStateId
    : (zeroIndegreeIds[0] ?? nodeIds[0])
  const rootOrder = uniqueIds([
    effectiveInitialId,
    ...zeroIndegreeIds,
    ...nodeIds
  ])

  const mainIds = collectReachable(effectiveInitialId, outgoing)
  const regions = [{ ids: mainIds, preferredRootId: effectiveInitialId }]
  const assigned = new Set(mainIds)

  for (const rootId of rootOrder) {
    if (assigned.has(rootId)) continue
    const regionIds = collectWeakComponent(rootId, outgoing, incoming, assigned)
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
    let maximumRows = 1

    for (const [layer, ids] of layers) {
      maximumRows = Math.max(maximumRows, ids.length)
      ids.forEach((id, row) => {
        coordinates.set(id, {
          x: WORKFLOW_LAYOUT.marginX + layer * WORKFLOW_LAYOUT.layerGap,
          y: regionTop + row * WORKFLOW_LAYOUT.rowGap
        })
      })
    }

    regionTop += (maximumRows + 1) * WORKFLOW_LAYOUT.rowGap
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

  const layersByIndex = new Map()
  for (const id of sortedIds) {
    const layer = levelById.get(id)
    if (!layersByIndex.has(layer)) layersByIndex.set(layer, [])
    layersByIndex.get(layer).push(id)
  }

  return [...layersByIndex.entries()].sort(([left], [right]) => left - right)
}

function collectReachable(rootId, outgoing) {
  const visited = new Set()
  const pending = [rootId]

  while (pending.length) {
    const id = pending.pop()
    if (visited.has(id)) continue
    visited.add(id)
    outgoing.get(id).forEach((targetId) => pending.push(targetId))
  }

  return visited
}

function collectWeakComponent(rootId, outgoing, incoming, excluded) {
  const visited = new Set()
  const pending = [rootId]

  while (pending.length) {
    const id = pending.pop()
    if (visited.has(id) || excluded.has(id)) continue
    visited.add(id)
    outgoing.get(id).forEach((neighborId) => pending.push(neighborId))
    incoming.get(id).forEach((neighborId) => pending.push(neighborId))
  }

  return visited
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
