import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./ProjectsView.vue', import.meta.url), 'utf8')

assert.match(
  source,
  /parent_id:\s*form\.parent_id\s*\|\|\s*null/,
  'Clearing the parent selector must send parent_id: null in the update payload'
)

console.log('project parent clear payload contract passed')
