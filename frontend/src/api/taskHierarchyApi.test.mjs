import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./tasks.js', import.meta.url), 'utf8')

assert.match(source, /export function fetchTaskChildren\(id, params = \{\}\)/)
assert.match(source, /http\.get\(`\/tasks\/\$\{id\}\/children`, \{ params \}\)/)

console.log('task hierarchy API contract passed')
