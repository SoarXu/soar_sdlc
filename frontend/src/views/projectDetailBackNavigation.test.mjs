import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const cases = [
  ['RequirementDetailView.vue', 'requirements'],
  ['TaskDetailView.vue', 'tasks'],
  ['TestCaseDetailView.vue', 'tests'],
  ['BugDetailView.vue', 'bugs']
]

const sources = Object.fromEntries(await Promise.all(cases.map(async ([name]) => [
  name,
  (await readFile(new URL(`./${name}`, import.meta.url), 'utf8')).replace(/\r\n/g, '\n')
])))

test('project-origin detail back navigation preserves project list query state', () => {
  for (const [name, tab] of cases) {
    const source = sources[name]
    assert.match(source, /route\.query\.from\s*===\s*['"]project['"]/, `${name} must detect project origin`)
    const branch = source.match(new RegExp(`route\\.query\\.from\\s*===\\s*['"]project['"][\\s\\S]{0,500}`))?.[0] || ''
    assert.match(branch, /query:\s*\{[\s\S]*\.\.\.route\.query/, `${name} must preserve query state`)
    assert.match(branch, new RegExp(`tab\\s*:\\s*['"]${tab}['"]`), `${name} must set tab=${tab}`)
  }
})

test('test case project return preserves test_tab when supplied', () => {
  const source = sources['TestCaseDetailView.vue']
  const branch = source.match(/route\.query\.from\s*===\s*['"]project['"][\s\S]{0,500}/)?.[0] || ''
  assert.match(branch, /\.\.\.route\.query/, 'test case return must preserve test_tab and other list state')
})
