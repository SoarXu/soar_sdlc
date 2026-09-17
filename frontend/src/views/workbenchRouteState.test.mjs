import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./DashboardView.vue', import.meta.url), 'utf8')

assert.match(source, /useRoute\(\)/, 'DashboardView should read the current route')
assert.match(source, /onBeforeUnmount/, 'DashboardView should clean up on unmount')
assert.match(source, /watch\(\(\) => route\.query/, 'DashboardView should react to route query navigation')
assert.match(source, /workbenchRouteStateEqual|routeStateEquals|isSameWorkbenchRouteState/, 'route watcher should avoid duplicate loads for equivalent state')
assert.match(source, /\.\.\/utils\/workbenchRouteState/, 'DashboardView should use the shared route state utility')
assert.match(source, /parse(?:Workbench)?RouteState/, 'DashboardView should parse workbench state from the route')
assert.match(source, /serialize(?:Workbench)?RouteState/, 'DashboardView should serialize workbench state into the route')
assert.match(source, /router\.replace\(/, 'DashboardView should synchronize state with the URL without adding history entries')
assert.match(source, /workbenchRouteQuery\(\)/, 'detail links should carry the current workbench query state')
assert.match(source, /keyword: keywordFilter\.value/, 'serialized detail query should include filters')
assert.match(source, /page: currentPage\.value/, 'serialized detail query should include the current page')
assert.match(source, /pageSize: pageSize\.value/, 'serialized detail query should include the current page size')

console.log('workbench route state contract passed')
