export function requirementEditPayload(form, projectId) {
  return {
    project_id: projectId,
    iteration_id: form.iteration_id,
    title: form.title,
    requirement_type: form.requirement_type,
    priority: form.priority,
    proposer: form.proposer || null,
    description: form.description,
    acceptance_criteria: form.acceptance_criteria
  }
}
