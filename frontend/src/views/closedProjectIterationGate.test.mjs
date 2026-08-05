import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const iterations = await readFile(new URL('./IterationsView.vue', import.meta.url), 'utf8')
const projectDetail = await readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8')

assert.match(iterations, /project\.state_category !== 'terminal'/)
assert.match(projectDetail, /canManageCurrentProject && !projectClosed/)

console.log('closed project iteration gate contract passed')
