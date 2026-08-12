export const ELIGIBLE_REQUIREMENT_ITERATION_CATEGORIES = new Set([
  'start',
  'normal',
  'in_progress'
])

export function deliveryIterations(items = []) {
  return items
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
  const scopedProjectIds = new Set(projectAncestorIds(projects, project?.id))
  return items.filter((item) => (
    ELIGIBLE_REQUIREMENT_ITERATION_CATEGORIES.has(item.state_category)
    && (item.project_ids || []).some((projectId) => scopedProjectIds.has(projectId))
  ))
}

export function requirementIterationLabel(iteration) {
  return iteration?.name || ''
}
