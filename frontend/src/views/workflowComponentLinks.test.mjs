import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./WorkflowView.vue', import.meta.url), 'utf8')

assert.match(source, /fetchBusinessComponents/)
assert.match(source, /componentLinksForConfig/)
assert.match(source, /关联项目与组件/)
assert.match(source, /workflow_scheme_id/)

console.log('workflow component link display contract passed')
