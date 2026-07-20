export function combineWorkflowDragViews(fullViews, previewViews, draggedStateId) {
  if (draggedStateId == null) return fullViews

  const fullByKey = new Map(fullViews.map((view) => [view.key, view]))
  return previewViews.map((preview) => {
    const incident = preview.transition.from_state_id === draggedStateId ||
      preview.transition.to_state_id === draggedStateId
    return incident ? preview : (fullByKey.get(preview.key) || preview)
  })
}
