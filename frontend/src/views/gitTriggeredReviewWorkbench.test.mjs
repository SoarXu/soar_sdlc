import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const dashboardSource = await readFile(new URL('./DashboardView.vue', import.meta.url), 'utf8')
const devopsSource = await readFile(new URL('./DevopsView.vue', import.meta.url), 'utf8')
const apiSource = await readFile(new URL('../api/devops.js', import.meta.url), 'utf8')

test('workbench exposes a pending-my-review section with a review entry action', () => {
  assert.match(dashboardSource, /待我评审/)
  assert.match(dashboardSource, /work_item_reviews/)
  assert.match(dashboardSource, /openWorkItemReview/)
})

test('workbench and DevOps use the shared work item review dialog', () => {
  assert.match(devopsSource, /工作项评审/)
  assert.match(dashboardSource, /WorkItemReviewDialog/)
  assert.match(devopsSource, /WorkItemReviewDialog/)
  assert.match(dashboardSource, /openWorkbenchReviewDialog/)
  assert.match(devopsSource, /openReviewDialog/)
  assert.doesNotMatch(dashboardSource, /decideWorkbenchReview/)
  assert.doesNotMatch(devopsSource, /decideReview/)
  assert.match(apiSource, /\/devops\/work-item-reviews/)
  assert.match(apiSource, /\/context/)
})
