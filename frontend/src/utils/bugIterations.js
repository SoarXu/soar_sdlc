export function projectAncestorIds(projects, projectId) {
  const ids = []
  const projectById = new Map(projects.map((project) => [project.id, project]))
  const visited = new Set()
  let currentId = projectId

  while (currentId && !visited.has(currentId)) {
    visited.add(currentId)
    ids.push(currentId)
    currentId = projectById.get(currentId)?.parent_id || null
  }

  return ids
}

export function bugIterationOptions(iterations, projects, projectId) {
  if (!projectId) {
    return iterations.filter((iteration) => iteration.state_category !== 'terminal')
  }

  const scopedProjectIds = new Set(projectAncestorIds(projects, projectId))
  return iterations.filter((iteration) => {
    if (iteration.state_category === 'terminal') return false
    return (iteration.project_ids || []).some((id) => scopedProjectIds.has(id))
  })
}

export function includeSelectedIterationOption(options, iterations, selectedId) {
  if (!selectedId || options.some((item) => item.id === selectedId)) return options
  const selected = iterations.find((item) => item.id === selectedId)
  return selected ? [...options, { ...selected, disabled: true }] : options
}
