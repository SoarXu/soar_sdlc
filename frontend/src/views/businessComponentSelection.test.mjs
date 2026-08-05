import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const viewFiles = [
  'RequirementsView.vue',
  'TasksView.vue',
  'BugsView.vue',
  'ProjectDetailView.vue'
]

for (const file of viewFiles) {
  const source = await readFile(new URL(`./${file}`, import.meta.url), 'utf8')
  assert.match(source, /BusinessComponentSelect/)
  assert.match(source, /primary_component_id/)
}

const selector = await readFile(new URL('../components/work-items/BusinessComponentSelect.vue', import.meta.url), 'utf8')
assert.match(selector, /fetchBusinessComponents/)
assert.match(selector, /enabledComponents/)
assert.match(selector, /update:modelValue/)

console.log('business component selection contract passed')
