import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const names = ['RequirementDetailView.vue', 'TaskDetailView.vue', 'BugDetailView.vue']
const sources = Object.fromEntries(await Promise.all(names.map(async (name) => [
  name,
  await readFile(new URL(`./${name}`, import.meta.url), 'utf8')
])))

test('dashboard detail back navigation carries workbench query state', () => {
  for (const name of names) {
    const source = sources[name]
    assert.match(source, /from === ['"]dashboard['"]/, name)
    assert.match(source, /query:\s*\{[^}]*\.\.\.route\.query/, name)
  }
})
