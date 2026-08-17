import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  buildWorkbenchViewModel,
  filterWorkbenchItems,
  isTerminalWorkItem,
  itemStatusLabel,
  itemStatusTag,
  paginateWorkbenchItems,
  sortWorkbenchItems,
  shouldShowWorkbenchWorkflowActions,
  workbenchInlineActions,
  workbenchItemActionGroup,
  workbenchMetaText
} from './workbenchViewModel.js'

{
  const items = Array.from({ length: 45 }, (_, index) => ({ id: index + 1 }))
  const originalItems = [...items]

  assert.deepEqual(paginateWorkbenchItems(items, 1, 20), {
    items: items.slice(0, 20),
    page: 1,
    pageSize: 20,
    total: 45,
    pageCount: 3
  })
  assert.deepEqual(paginateWorkbenchItems(items, 2, 20), {
    items: items.slice(20, 40),
    page: 2,
    pageSize: 20,
    total: 45,
    pageCount: 3
  })
  assert.deepEqual(items, originalItems)
}

{
  assert.deepEqual(paginateWorkbenchItems([], 8, 20), {
    items: [],
    page: 1,
    pageSize: 20,
    total: 0,
    pageCount: 1
  })
}

{
  const items = Array.from({ length: 25 }, (_, index) => ({ id: index + 1 }))

  assert.equal(paginateWorkbenchItems(items, 0, 10).page, 1)
  assert.equal(paginateWorkbenchItems(items, 99, 10).page, 3)
  assert.deepEqual(paginateWorkbenchItems(items, 99, 10).items, items.slice(20))
}

{
  const items = Array.from({ length: 25 }, (_, index) => ({ id: index + 1 }))
  const result = paginateWorkbenchItems(items, 1, 0)

  assert.equal(result.pageSize, 20)
  assert.equal(result.pageCount, 2)
  assert.deepEqual(result.items, items.slice(0, 20))
}

{
  const items = Array.from({ length: 25 }, (_, index) => ({ id: index + 1 }))

  for (const invalidPageSize of [Infinity, -Infinity, Number.NaN, Number.MIN_VALUE, 0.5, true, false, 'not-a-number']) {
    const result = paginateWorkbenchItems(items, 1, invalidPageSize)
    assert.equal(result.pageSize, 20)
    assert.equal(result.pageCount, 2)
    assert.deepEqual(result.items, items.slice(0, 20))
  }
  assert.equal(paginateWorkbenchItems(items, 1, '10').pageSize, 10)
}

{
  const items = Array.from({ length: 25 }, (_, index) => ({ id: index + 1 }))

  for (const invalidPage of [Infinity, -Infinity, Number.NaN, Number.MIN_VALUE, 0.5, true, false, 'not-a-number']) {
    assert.equal(paginateWorkbenchItems(items, invalidPage, 10).page, 1)
  }
  assert.equal(paginateWorkbenchItems(items, '2', 10).page, 2)
}

{
  const dashboardSource = readFileSync(new URL('../views/DashboardView.vue', import.meta.url), 'utf8')

  assert.match(dashboardSource, /const currentPage = ref\(1\)/)
  assert.match(dashboardSource, /const pageSize = ref\(20\)/)
  assert.match(dashboardSource, /const pagedListPage = computed\(\(\) => paginateWorkbenchItems\(/)
  assert.match(dashboardSource, /const pagedListItems = computed\(\(\) => pagedListPage\.value\.items\)/)
  assert.match(dashboardSource, /<el-table[^>]*:data="pagedListItems"/)
  assert.match(dashboardSource, /<el-pagination[\s\S]*?v-model:current-page="currentPage"/)
  assert.match(dashboardSource, /<el-pagination[\s\S]*?v-model:page-size="pageSize"/)
  assert.match(dashboardSource, /:page-sizes="\[10, 20, 50, 100\]"/)
  assert.match(dashboardSource, /function resetWorkbenchPagination\(\)[\s\S]*?clearWorkbenchSelection\(\)[\s\S]*?currentPage\.value = 1/)
  assert.match(dashboardSource, /watch\(\[[\s\S]*?handlerFilter[\s\S]*?\], resetWorkbenchPagination, \{ deep: true \}\)/)
  assert.match(dashboardSource, /watch\(\(\) => pagedListPage\.value\.page, \(correctedPage\) =>[\s\S]*?currentPage\.value = correctedPage/)
  assert.match(dashboardSource, /class="workbench-list-table"[\s\S]*?<\/div>\s*<footer class="workbench-pagination-footer"/)
  const emptyStateIndex = dashboardSource.indexOf('<el-empty v-if="!filteredListItems.length"')
  const paginationFooterIndex = dashboardSource.indexOf('<footer class="workbench-pagination-footer">')
  assert.ok(emptyStateIndex >= 0)
  assert.ok(paginationFooterIndex > emptyStateIndex)
  assert.doesNotMatch(dashboardSource.slice(paginationFooterIndex, dashboardSource.indexOf('>', paginationFooterIndex) + 1), /v-if/)

  const batchAssignmentFooterRule = dashboardSource.match(/\.workbench-batch-assignment-footer\s*\{[^}]*\}/)
  assert.ok(batchAssignmentFooterRule)
  assert.match(batchAssignmentFooterRule[0], /position\s*:\s*static/)
  assert.match(batchAssignmentFooterRule[0], /flex\s*:\s*0\s+0\s+auto/)
  assert.doesNotMatch(batchAssignmentFooterRule[0], /position\s*:\s*(?:absolute|sticky)/)
}

{
  const styles = readFileSync(new URL('../styles.css', import.meta.url), 'utf8')
  const workbenchPageRule = styles.match(/\.workbench-page\s*\{[^}]*\}/)
  const workbenchListRule = styles.match(/\.workbench-list\s*\{[^}]*\}/)
  const listSectionRule = styles.match(/\.workbench-list-section\s*\{[^}]*\}/)
  const listTableRule = styles.match(/\.workbench-list-table\s*\{[^}]*\}/)
  const elementTableRule = styles.match(/\.workbench-list-table \.el-table\s*\{[^}]*\}/)
  const paginationFooterRule = styles.match(/\.workbench-pagination-footer\s*\{[^}]*\}/)

  assert.ok(workbenchPageRule)
  assert.match(workbenchPageRule[0], /display\s*:\s*(?:flex|grid)/)
  assert.match(workbenchPageRule[0], /flex\s*:\s*1/)
  assert.match(workbenchPageRule[0], /min-height\s*:\s*0/)
  for (const rule of [workbenchListRule, listSectionRule, listTableRule]) {
    assert.ok(rule)
    assert.match(rule[0], /flex\s*:\s*1/)
    assert.match(rule[0], /min-height\s*:\s*0/)
  }
  assert.doesNotMatch(listTableRule[0], /max-height/)
  assert.match(listTableRule[0], /overflow\s*:\s*hidden/)
  assert.match(listTableRule[0], /display\s*:\s*flex/)
  assert.match(listTableRule[0], /flex-direction\s*:\s*column/)
  assert.ok(elementTableRule)
  assert.match(elementTableRule[0], /flex\s*:\s*1\s+1\s+auto/)
  assert.match(elementTableRule[0], /min-height\s*:\s*0/)
  assert.ok(paginationFooterRule)
  assert.match(paginationFooterRule[0], /flex\s*:\s*0\s+0\s+auto/)

  const mobileWorkbenchRules = styles.match(
    /@media\s*\(max-width:\s*720px\)\s*\{\s*\.workbench-page\s*\{([^}]*)\}\s*\.workbench-list\s*\{([^}]*)\}/
  )
  assert.ok(mobileWorkbenchRules)
  assert.match(mobileWorkbenchRules[1], /overflow-x\s*:\s*hidden/)
  assert.match(mobileWorkbenchRules[1], /overflow-y\s*:\s*auto/)
  assert.match(mobileWorkbenchRules[2], /flex\s*:\s*0\s+0\s+auto/)
  assert.match(mobileWorkbenchRules[2], /min-height\s*:\s*(?:clamp\(|420px)/)
}

{
  const styles = readFileSync(new URL('../styles.css', import.meta.url), 'utf8')
  const terminalTitleRule = styles.match(/\.workbench-title-button\.is-terminal\s*\{[^}]*\}/)

  assert.ok(terminalTitleRule)
  assert.doesNotMatch(terminalTitleRule[0], /text-decoration\s*:\s*line-through/)
}

{
  const items = [
    {
      id: 1,
      object_type: 'bug',
      project_id: 10,
      priority: '1',
      current_state_id: 101,
      status_name: '团队修复阶段',
      owner_id: 7,
      handler_id: 8,
      overdue_hours: 6
    },
    {
      id: 2,
      object_type: 'task',
      project_id: 11,
      priority: '3',
      current_state_id: 202,
      status_name: '处理中',
      owner_id: 9,
      handler_id: 9,
      overdue_hours: 2
    }
  ]

  assert.deepEqual(filterWorkbenchItems(items, {
    projectIds: [10],
    types: ['bug'],
    priorities: ['1'],
    stateIds: [101],
    ownerIds: [7],
    handlerIds: [8],
    minOverdueHours: 6
  }).map((item) => item.id), [1])
  assert.deepEqual(filterWorkbenchItems(items, { minOverdueHours: 7 }), [])
}

{
  const items = [
    {
      id: 1,
      object_type: 'bug',
      title: 'Alpha regression',
      project_id: 10,
      iteration_id: 100,
      priority: '1',
      current_state_id: 101,
      owner_id: 7,
      handler_id: 8
    },
    {
      id: 2,
      object_type: 'task',
      title: 'Beta delivery',
      project_id: 11,
      iteration_id: 101,
      priority: '2',
      current_state_id: 202,
      owner_id: 9,
      handler_id: 10
    },
    {
      id: 3,
      object_type: 'requirement',
      title: 'Gamma capability',
      project_id: 12,
      iteration_id: 102,
      priority: '3',
      current_state_id: 303,
      owner_id: 11,
      handler_id: 12
    }
  ]

  assert.deepEqual(filterWorkbenchItems(items, { keyword: 'alpha' }).map((item) => item.id), [1])
  assert.deepEqual(filterWorkbenchItems(items, { projectIds: [10] }).map((item) => item.id), [1])
  assert.deepEqual(filterWorkbenchItems(items, { iterationIds: [100] }).map((item) => item.id), [1])
  assert.deepEqual(filterWorkbenchItems(items, { types: ['bug'] }).map((item) => item.id), [1])
  assert.deepEqual(filterWorkbenchItems(items, { stateIds: [101] }).map((item) => item.id), [1])
  assert.deepEqual(filterWorkbenchItems(items, { priorities: ['1'] }).map((item) => item.id), [1])
  assert.deepEqual(filterWorkbenchItems(items, { ownerIds: [7] }).map((item) => item.id), [1])
  assert.deepEqual(filterWorkbenchItems(items, { handlerIds: [8] }).map((item) => item.id), [1])
  assert.deepEqual(
    filterWorkbenchItems(items, { projectIds: [10], stateIds: [101], handlerIds: [8] }).map((item) => item.id),
    [1]
  )
}

{
  const items = [
    { id: 1, object_type: 'task', state_category: 'active', overdue_hours: 0, priority: 'high', due_date: '2026-08-30', update_time: '2026-08-11T08:00:00' },
    { id: 2, object_type: 'task', state_category: 'active', overdue_hours: 0, priority: 'medium', due_date: '2026-08-01', update_time: '2026-08-11T10:00:00' },
    { id: 3, object_type: 'task', state_category: 'active', overdue_hours: 0, priority: 'low', due_date: '2026-08-01', update_time: '2026-08-11T12:00:00' },
    { id: 4, object_type: 'requirement', state_category: 'active', overdue_hours: 0, priority: '1', due_date: '2026-08-31', update_time: '2026-08-11T09:00:00' },
    { id: 5, object_type: 'bug', state_category: 'active', overdue_hours: 0, severity: '2', due_date: '2026-08-01', update_time: '2026-08-11T11:00:00' }
  ]

  assert.deepEqual(sortWorkbenchItems(items).map((item) => item.id), [1, 4, 5, 2, 3])
}

{
  const items = [
    { id: 1, object_type: 'requirement', state_category: 'active', overdue_hours: 4, priority: '1', due_date: '2026-08-12', update_time: '2026-08-11T12:00:00' },
    { id: 2, object_type: 'task', state_category: 'active', overdue_hours: 1, priority: '1', due_date: '2026-08-11', update_time: '2026-08-11T11:00:00' },
    { id: 3, object_type: 'bug', state_category: 'active', overdue_hours: 2, priority: '3', due_date: '2026-08-10', update_time: '2026-08-11T10:00:00' },
    { id: 4, object_type: 'task', state_category: 'active', overdue_hours: 0, priority: '1', due_date: '2026-08-01', update_time: '2026-08-11T09:00:00' },
    { id: 5, object_type: 'bug', state_category: 'active', overdue_hours: 0, priority: '1', due_date: '2026-08-20', update_time: '2026-08-11T20:00:00' },
    { id: 6, object_type: 'requirement', state_category: 'active', overdue_hours: 0, priority: '1', due_date: '2026-08-20', update_time: '2026-08-11T18:00:00' },
    { id: 7, object_type: 'task', state_category: 'terminal', terminal_kind: 'completed', overdue_hours: 8, priority: '1', due_date: '2026-08-01', update_time: '2026-08-11T22:00:00' },
    { id: 8, object_type: 'bug', state_category: 'terminal', terminal_kind: 'cancelled', overdue_hours: 0, priority: '1', due_date: '2026-08-30', update_time: '2026-08-11T23:00:00' },
    { id: 9, object_type: 'requirement', state_category: 'active', overdue_hours: 0, priority: '1', due_date: null, update_time: '2026-08-11T23:30:00' }
  ]

  assert.deepEqual(
    sortWorkbenchItems(items).map((item) => item.id),
    [2, 1, 3, 4, 5, 6, 9, 7, 8]
  )
}

{
  const item = {
    object_type: 'bug',
    current_state_id: 101,
    status_name: '团队自定义完成',
    state_category: 'terminal'
  }
  assert.equal(itemStatusLabel(item), '团队自定义完成')
  assert.equal(isTerminalWorkItem(item), true)
}

{
  assert.equal(itemStatusTag({ object_type: 'bug', state_category: 'terminal', terminal_kind: 'completed' }), 'success')
  assert.equal(itemStatusTag({ object_type: 'bug', state_category: 'terminal', terminal_kind: 'terminated' }), 'info')
  assert.equal(itemStatusTag({ object_type: 'bug', state_category: 'terminal', terminal_kind: null }), 'info')
  assert.equal(itemStatusTag({ object_type: 'bug', state_category: 'terminal', terminal_kind: 'unexpected' }), 'info')
}

{
  const viewModel = buildWorkbenchViewModel({
    pending_handling: { label: '待处理', items: [{ id: 1, object_type: 'task' }], total: 1 },
    unassigned: { label: '未分派', items: [{ id: 2, object_type: 'bug' }], total: 1 },
    unplanned: { label: '待规划', items: [{ id: 6, object_type: 'requirement' }], total: 1 },
    exception_center: { label: '异常中心', items: [], total: 0 },
    created_by_me: { label: '我发起的', items: [{ id: 3, object_type: 'requirement' }], total: 1 },
    watched_by_me: { label: '我关注的', items: [{ id: 4, object_type: 'task' }], total: 1 },
    mentioned_me: { label: '提到我的', items: [{ id: 5, object_type: 'bug' }], total: 1 }
  })

  assert.deepEqual(viewModel.entryTabs.map((section) => section.key), [
    'pending_handling',
    'unassigned',
    'completed',
    'terminated',
    'exception_center',
    'following'
  ])
  assert.equal(viewModel.summaryCards[0].value, 1)
  assert.equal('unplanned' in viewModel.queueSectionsByKey, false)
  assert.equal(viewModel.summaryCards.some((card) => card.key === 'unplanned'), false)
  assert.equal(viewModel.summaryCards.length, 6)
}

{
  const dashboardSource = readFileSync(new URL('../views/DashboardView.vue', import.meta.url), 'utf8')

  assert.doesNotMatch(dashboardSource, /include[_A-Z]?history|history[_A-Z]?switch|iteration[_A-Z]?range/i)
}

{
  const viewModel = buildWorkbenchViewModel({
    created_by_me: { label: '我发起的', items: [{ id: 1 }], total: 1 },
    watched_by_me: { label: '我关注的', items: [{ id: 2 }], total: 1 },
    mentioned_me: { label: '提到我的', items: [{ id: 3 }], total: 1 }
  })

  assert.deepEqual(viewModel.trackingTabs.map((tab) => tab.key), [
    'created_by_me',
    'watched_by_me',
    'mentioned_me'
  ])
  assert.equal(viewModel.trackingTabsByKey.mentioned_me.total, 1)
  assert.equal(viewModel.trackingTabsByKey.mentioned_me.description, '评论中通过 @ 提及到我的评论。')
}

{
  const dashboardSource = readFileSync(new URL('../views/DashboardView.vue', import.meta.url), 'utf8')

  assert.match(dashboardSource, /active_iteration_items/)
  assert.match(dashboardSource, /v-model="projectFilter"/)
  assert.match(dashboardSource, /v-model="iterationFilter"/)
  assert.match(dashboardSource, /v-model="stateFilter"/)
  assert.match(dashboardSource, /v-model="priorityFilter"/)
  assert.match(dashboardSource, /v-model="ownerFilter"/)
  assert.match(dashboardSource, /v-model="handlerFilter"/)
  assert.doesNotMatch(dashboardSource, /activeListSection|workbench-entry-switch|workbench-follow-tabs|exception-filter-toolbar/)
}

{
  const stylesSource = readFileSync(new URL('../styles.css', import.meta.url), 'utf8')

  assert.match(stylesSource, /\.workbench-filter\s*\{\s*flex:\s*0 0 260px;\s*min-width:\s*160px;\s*max-width:\s*260px;\s*width:\s*260px;/)
  assert.match(stylesSource, /\.workbench-search\s*\{\s*flex:\s*0 0 260px;\s*min-width:\s*160px;\s*max-width:\s*260px;\s*width:\s*260px;/)
}

{
  assert.equal(workbenchMetaText('exception_center', { exception_label: '已验证未关闭' }), '已验证未关闭')
  assert.equal(workbenchMetaText('watched_by_me', { watch_source: 'mention' }), '评论提及自动关注')
  assert.equal(workbenchMetaText('mentioned_me', { mentioned_in_comment_id: 18 }), '评论 #18')
}

{
  const dashboardSource = readFileSync(new URL('../views/DashboardView.vue', import.meta.url), 'utf8')

  assert.match(dashboardSource, /<el-table-column label="负责人" width="130">/)
  assert.match(dashboardSource, /<el-table-column label="当前处理人" width="130">/)
}

{
  assert.equal(
    workbenchMetaText('exception_center', { exception_label: 'Timed out', overdue_hours: 6 }),
    'Timed out - overdue 6h'
  )
  assert.equal(
    workbenchMetaText('exception_center', {
      exception_label: 'Current owner is ineligible',
      exception_details: [
        { exception_key: 'owner_ineligible', exception_label: 'Current owner is ineligible', exception_detail: 'Owner lacks a core action' },
        { exception_key: 'iteration_history_inconsistent', exception_label: 'Iteration history is inconsistent', exception_detail: 'Open history does not match' }
      ]
    }),
    'Current owner is ineligible：Owner lacks a core action；Iteration history is inconsistent：Open history does not match'
  )
}

{
  const failedCase = workbenchItemActionGroup('pending_handling', {
    object_type: 'test_case',
    last_execute_result: 'failed'
  })
  const unassignedBug = workbenchItemActionGroup('unassigned', {
    object_type: 'bug'
  })

  assert.equal(failedCase.primary.key, 'execute_case')
  assert.deepEqual(failedCase.secondary.map((item) => item.key), ['create_case_bug'])
  assert.equal(unassignedBug.primary, null)
  assert.deepEqual(unassignedBug.secondary, [])
}

{
  const actions = workbenchInlineActions('unassigned', { object_type: 'bug' })

  assert.deepEqual(actions, [])
}

{
  assert.equal(shouldShowWorkbenchWorkflowActions('unassigned', { object_type: 'requirement' }), true)
  assert.equal(shouldShowWorkbenchWorkflowActions('unassigned', { object_type: 'task' }), true)
  assert.equal(shouldShowWorkbenchWorkflowActions('unassigned', { object_type: 'bug' }), true)
  assert.equal(shouldShowWorkbenchWorkflowActions('pending_handling', { object_type: 'requirement' }), true)
  assert.equal(shouldShowWorkbenchWorkflowActions('exception_center', { object_type: 'bug' }), true)
  assert.equal(shouldShowWorkbenchWorkflowActions('pending_handling', { object_type: 'test_case' }), false)
}

console.log('workbenchViewModel tests passed')
