import assert from 'node:assert/strict'

import {
  buildWorkbenchViewModel,
  filterWorkbenchItems,
  shouldShowWorkbenchWorkflowActions,
  workbenchInlineActions,
  workbenchItemActionGroup,
  workbenchMetaText
} from './workbenchViewModel.js'

{
  const items = [
    {
      id: 1,
      object_type: 'bug',
      project_id: 10,
      priority: '1',
      status: 'fixing',
      owner_id: 7,
      handler_id: 8,
      overdue_hours: 6
    },
    {
      id: 2,
      object_type: 'task',
      project_id: 11,
      priority: '3',
      status: 'in_processing',
      owner_id: 9,
      handler_id: 9,
      overdue_hours: 2
    }
  ]

  assert.deepEqual(filterWorkbenchItems(items, {
    projectIds: [10],
    types: ['bug'],
    priorities: ['1'],
    statuses: ['fixing'],
    ownerIds: [7],
    handlerIds: [8],
    minOverdueHours: 6
  }).map((item) => item.id), [1])
  assert.deepEqual(filterWorkbenchItems(items, { minOverdueHours: 7 }), [])
}

{
  const viewModel = buildWorkbenchViewModel({
    pending_handling: { label: '待处理', items: [{ id: 1, object_type: 'task' }], total: 1 },
    unassigned: { label: '未分派', items: [{ id: 2, object_type: 'bug' }], total: 1 },
    exception_center: { label: '异常中心', items: [], total: 0 },
    created_by_me: { label: '我发起的', items: [{ id: 3, object_type: 'requirement' }], total: 1 },
    watched_by_me: { label: '我关注的', items: [{ id: 4, object_type: 'task' }], total: 1 },
    mentioned_me: { label: '提到我的', items: [{ id: 5, object_type: 'bug' }], total: 1 }
  })

  assert.deepEqual(viewModel.entryTabs.map((section) => section.key), [
    'pending_handling',
    'unassigned',
    'exception_center',
    'following'
  ])
  assert.equal(viewModel.summaryCards[0].value, 1)
  assert.equal(viewModel.summaryCards.length, 4)
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
}

{
  assert.equal(workbenchMetaText('exception_center', { exception_label: '已验证未关闭' }), '已验证未关闭')
  assert.equal(workbenchMetaText('watched_by_me', { watch_source: 'mention' }), '评论提及自动关注')
  assert.equal(workbenchMetaText('mentioned_me', { mentioned_in_comment_id: 18 }), '评论 #18')
}

{
  assert.equal(
    workbenchMetaText('exception_center', { exception_label: 'Timed out', overdue_hours: 6 }),
    'Timed out - overdue 6h'
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
