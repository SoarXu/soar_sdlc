import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./ProjectComponentsView.vue', import.meta.url), 'utf8')

assert.match(source, /fetchBusinessComponents/)
assert.match(source, /fetchUsers/)
assert.match(source, /memberLabel\(row\.members\)/)
assert.match(source, /function memberLabel\(members\)/)

console.log('project components member display contract passed')
