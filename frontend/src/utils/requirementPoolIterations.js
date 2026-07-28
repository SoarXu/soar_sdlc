export function deliveryIterations(items = []) {
  return items.filter((item) => !item.is_requirement_pool)
}

export function requirementPoolForProject(project, items = []) {
  const poolId = project?.requirement_pool_iteration_id
  if (!poolId) return null

  return items.find((item) => (
    item.id === poolId && item.is_requirement_pool
  )) || null
}

function projectAncestorIds(projects = [], projectId) {
  const projectById = new Map(projects.map((project) => [project.id, project]))
  const ancestorIds = []
  const visited = new Set()
  let currentId = projectId

  while (currentId && !visited.has(currentId)) {
    visited.add(currentId)
    ancestorIds.push(currentId)
    currentId = projectById.get(currentId)?.parent_id || null
  }

  return ancestorIds
}

export function requirementIterationOptions(project, projects = [], items = []) {
  const pool = requirementPoolForProject(project, items)
  const scopedProjectIds = new Set(projectAncestorIds(projects, project?.id))
  const scopedDeliveries = deliveryIterations(items).filter((item) => (
    (item.project_ids || []).some((projectId) => scopedProjectIds.has(projectId))
  ))

  return pool ? [pool, ...scopedDeliveries] : scopedDeliveries
}

export function requirementIterationLabel(iteration) {
  return iteration?.is_requirement_pool
    ? `${iteration.name}（未排期）`
    : iteration?.name || ''
}
