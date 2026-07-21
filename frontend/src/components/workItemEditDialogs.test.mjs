import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const components = [
  ['RequirementEditDialog.vue', 'fetchRequirement', 'updateRequirement'],
  ['TaskEditDialog.vue', 'fetchTask', 'updateTask'],
  ['BugEditDialog.vue', 'fetchBug', 'updateBug']
]

for (const [filename, fetchName, updateName] of components) {
  const source = await readFile(new URL(`./work-items/${filename}`, import.meta.url), 'utf8')
  assert.match(source, /modelValue/)
  assert.match(source, /itemId/)
  assert.match(source, /update:modelValue/)
  assert.match(source, /saved/)
  assert.match(source, new RegExp(fetchName))
  assert.match(source, new RegExp(updateName))
  assert.match(source, /showActionError/)
  assert.match(source, /watch\([\s\S]*?\{ immediate: true \}\)/)
}

const viewContracts = [
  ['../views/RequirementsView.vue', 'RequirementEditDialog'],
  ['../views/TasksView.vue', 'TaskEditDialog'],
  ['../views/BugsView.vue', 'BugEditDialog']
]

for (const [filename, componentName] of viewContracts) {
  const source = await readFile(new URL(filename, import.meta.url), 'utf8')
  assert.match(source, new RegExp(`import ${componentName}`))
  assert.match(source, new RegExp(`<${componentName}`))
}

console.log('work item edit dialog contracts passed')
