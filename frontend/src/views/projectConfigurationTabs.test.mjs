import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const [detailSource, componentSource, routerSource] = await Promise.all([
  readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8'),
  readFile(new URL('./ProjectComponentsView.vue', import.meta.url), 'utf8'),
  readFile(new URL('../router/index.js', import.meta.url), 'utf8')
])

assert.match(detailSource, /ProjectComponentsView/)
assert.match(detailSource, /settingsTab/)
assert.match(detailSource, /工作流方案/)
assert.match(detailSource, /业务组件/)
assert.doesNotMatch(detailSource, /name: 'project-components'/)
assert.match(componentSource, /defineProps/)
assert.match(componentSource, /embedded/)
assert.match(routerSource, /path: 'projects\/:id\/components'/)
assert.match(routerSource, /settingsTab: 'components'/)

console.log('project configuration tab contracts passed')
