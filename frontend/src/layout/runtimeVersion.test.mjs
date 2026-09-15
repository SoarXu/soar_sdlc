import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const layout = await readFile(new URL('./MainLayout.vue', import.meta.url), 'utf8')
const config = await readFile(new URL('../../vite.config.js', import.meta.url), 'utf8')

assert.match(layout, /v\{\{ frontendVersion \}\}/)
assert.match(layout, /fetchVersionInfo/)
assert.match(layout, /后端不可用/)
assert.match(layout, /数据库版本/)
assert.match(layout, /VITE_APP_VERSION \|\| '1\.0\.0'/)
assert.match(config, /VITE_RELEASE_BUILD/)
assert.match(config, /VITE_APP_VERSION/)

console.log('runtime version layout tests passed')
