import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const normalize = (source) => source.replace(/\r\n/g, '\n')
const projectDetail = normalize(await readFile(new URL('./ProjectDetailView.vue', import.meta.url), 'utf8'))
const workPoolBand = normalize(await readFile(new URL('../components/ProjectWorkPoolBand.vue', import.meta.url), 'utf8'))
const dashboard = normalize(await readFile(new URL('./DashboardView.vue', import.meta.url), 'utf8'))

assert.match(projectDetail, /import ProjectWorkPoolBand/)
assert.equal((projectDetail.match(/<ProjectWorkPoolBand/g) || []).length, 2)
assert.match(projectDetail, /:summary="projectUnfinishedWorkItems"/)
assert.match(projectDetail, /data\.unfinished_work_items/)
assert.match(projectDetail, /unfinished_work_items: filters\?\.unfinished_work_items/)
assert.match(projectDetail, /@view="openWorkPoolItems"/)
assert.doesNotMatch(projectDetail, /projectPlanningPool|planning_pool|planningPoolIterationIds/)
assert.doesNotMatch(projectDetail, /can-plan|@plan|openWorkPoolPlanning/)

for (const label of ['需求', '任务', 'Bug']) assert.match(workPoolBand, new RegExp(label))
assert.match(workPoolBand, /未完成工作项/)
assert.doesNotMatch(workPoolBand, /待规划/)
assert.doesNotMatch(workPoolBand, /canPlan|FolderAdd|emit\('plan'\)|纳入迭代/)
assert.doesNotMatch(dashboard, /ProjectWorkPoolBand|workPoolPlanning/)
assert.match(workPoolBand, /\.work-pool-band\s*\{[\s\S]*?box-sizing:\s*border-box;/)
assert.match(workPoolBand, /\.work-pool-band\s*\{[\s\S]*?width:\s*100%;/)

console.log('project planning work-pool contracts passed')
