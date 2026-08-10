import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const normalize = (source) => source.replace(/\r\n/g, '\n')
const projectDetail = normalize(await readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8'))
const workPoolBand = normalize(await readFile(new URL('../components/ProjectWorkPoolBand.vue', import.meta.url), 'utf8'))
const iterationsApi = normalize(await readFile(new URL('../api/iterations.js', import.meta.url), 'utf8'))
const dashboard = normalize(await readFile(new URL('./DashboardView.vue', import.meta.url), 'utf8'))

assert.match(projectDetail, /import ProjectWorkPoolBand from '\.\.\/components\/ProjectWorkPoolBand\.vue'/)
assert.equal((projectDetail.match(/<ProjectWorkPoolBand/g) || []).length, 2)
assert.match(projectDetail, /:summary="projectRequirementPool"/)
assert.match(projectDetail, /@view="openWorkPoolItems"/)
assert.match(projectDetail, /@plan="openWorkPoolPlanning"/)
assert.doesNotMatch(projectDetail, /\[projectRequirementPoolRow\.value, \.\.\.projectIterations\.value\]/)

assert.match(workPoolBand, /待规划 \{\{ totalCount \}\} 项/)
assert.match(workPoolBand, /需求/)
assert.match(workPoolBand, /任务/)
assert.match(workPoolBand, /Bug/)
assert.match(workPoolBand, /查看事项/)
assert.match(workPoolBand, /纳入迭代/)

for (const key of ['requirements', 'tasks', 'bugs']) {
  assert.match(projectDetail, new RegExp(`projectListFilters\\.${key}\\.iteration_id`))
}
assert.match(projectDetail, /iteration_id: filters\?\.iteration_id \|\| undefined/)
assert.match(projectDetail, /workPoolPlanningVisible/)
assert.match(projectDetail, /linkIterationRequirements/)
assert.match(projectDetail, /linkIterationTasks/)
assert.match(projectDetail, /linkIterationBugs/)
assert.match(iterationsApi, /export function linkIterationBugs/)

assert.doesNotMatch(dashboard, /ProjectWorkPoolBand|workPoolPlanning|待规划工作池/)

assert.match(
  workPoolBand,
  /\.work-pool-band\s*\{[\s\S]*?box-sizing:\s*border-box;/,
  'the full-width work-pool banner must include its borders and padding in its width'
)
assert.match(workPoolBand, /\.work-pool-band\s*\{[\s\S]*?width:\s*100%;/)

console.log('project planning work-pool contracts passed')
