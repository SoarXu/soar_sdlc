export function selectEnabledWorkflowDefinition(definitions) {
  return definitions.find((item) => item.enabled)
}
