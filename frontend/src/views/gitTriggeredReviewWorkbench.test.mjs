import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const dashboardSource = await readFile(new URL('./DashboardView.vue', import.meta.url), 'utf8')
const devopsSource = await readFile(new URL('./DevopsView.vue', import.meta.url), 'utf8')
const apiSource = await readFile(new URL('../api/devops.js', import.meta.url), 'utf8')

test('workbench keeps pending reviews in the unified active-iteration list', () => {
  assert.doesNotMatch(dashboardSource, /待我评审/)
  assert.doesNotMatch(dashboardSource, /workItemReviews/)
  assert.match(dashboardSource, /WorkflowActionButtons/)
})

test('DevOps uses the shared work item review dialog', () => {
  assert.match(devopsSource, /工作项评审/)
  assert.match(devopsSource, /WorkItemReviewDialog/)
  assert.match(devopsSource, /openReviewDialog/)
  assert.doesNotMatch(devopsSource, /decideReview/)
  assert.match(apiSource, /\/devops\/work-item-reviews/)
  assert.match(apiSource, /\/context/)
})
