import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const projectsSource = await readFile(new URL('./ProjectsView.vue', import.meta.url), 'utf8')
const programsSource = await readFile(new URL('./ProgramsView.vue', import.meta.url), 'utf8')
const apiSource = await readFile(new URL('../api/projects.js', import.meta.url), 'utf8')

assert.match(apiSource, /export function fetchProjectMembersBatch\(projectIds\)/)
assert.match(apiSource, /http\.post\('\/projects\/members\/batch', \{ project_ids: projectIds \}\)/)

for (const [label, source] of [['项目列表', projectsSource], ['项目集', programsSource]]) {
  assert.match(source, /fetchProjectMembersBatch/)
  assert.doesNotMatch(source, /allProjects\.value\.map\(async \(project\)/, `${label}不应逐项目请求成员`)
  assert.doesNotMatch(source, /fetchProjectMembers\(project\.id\)/, `${label}不应调用单项目成员接口`)
}

assert.match(projectsSource, /const visibleProjectIds = computed/)
assert.match(projectsSource, /flattenProjectTree\(pagedProjectTree\.value\)/)
assert.match(projectsSource, /visibleProjectIds\.value/)
assert.match(projectsSource, /watch\(\[projectPage, projectPageSize\]/)
assert.match(projectsSource, /requestVersion === memberRequestVersion\.value/)
assert.match(projectsSource, /requestVersion === transitionRequestVersion\.value/)

console.log('project page performance contracts passed')
