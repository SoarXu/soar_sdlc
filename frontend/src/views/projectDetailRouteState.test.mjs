import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8')

assert.match(source, /from ['"]\.\.\/utils\/projectDetailRouteState['"]/, '项目详情应使用统一路由状态工具')
assert.match(source, /parseProjectDetailRouteState\(route\.query\)/, '项目详情应从路由查询恢复列表状态')
assert.match(source, /projectDetailRouteQuery\(/, '列表状态变化应序列化回路由查询')
assert.match(source, /query:\s*\{\s*\.\.\.route\.query/, '详情链接应携带当前项目完整查询状态')

for (const name of ['requirements', 'tasks', 'testCases', 'testRuns', 'bugs']) {
  assert.match(source, new RegExp(`projectListFilters\\.${name}`), `${name} 应具有独立筛选状态`)
  assert.match(source, new RegExp(`projectListPagination\\.${name}`), `${name} 应具有独立分页状态`)
}

console.log('projectDetailRouteState view contract passed')
