import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const files = ['./ProjectDetailView.vue', './RequirementsView.vue', './RequirementDetailView.vue']
const sources = await Promise.all(files.map(async (file) => (
  (await readFile(new URL(file, import.meta.url), 'utf8')).replace(/\r\n/g, '\n')
)))

for (const source of sources) {
  assert.match(source, /requirementIterationOptions/)
  assert.match(source, /requirementIterationLabel/)
  assert.match(source, /fetchIterations\(\)/)
  assert.doesNotMatch(source, /include_requirement_pool|requirementPoolForProject|is_requirement_pool/)
  assert.doesNotMatch(source, /v-model="(?:requirementForm|form)\.iteration_id" clearable/)
}

assert.match(sources[0], /data\.unfinished_work_items/)
assert.match(sources[1], /!form\.iteration_id/)
assert.match(sources[2], /!requirementForm\.iteration_id/)

console.log('real iteration project view contracts passed')
