import assert from 'node:assert/strict'

import {
  buildProjectBoard,
  buildWorkbenchViewModel,
  workbenchItemActionGroup,
  workbenchMetaText
} from './workbenchViewModel.js'

{
  const viewModel = buildWorkbenchViewModel({
    pending_handling: { label: '待处理', items: [{ id: 1, object_type: 'task' }], total: 1 },
    unassigned: { label: '未分派', items: [{ id: 2, object_type: 'bug' }], total: 1 },
    exception_center: { label: '异常中心', items: [], total: 0 },
    created_by_me: { label: '我发起的', items: [{ id: 3, object_type: 'requirement' }], total: 1 },
    watched_by_me: { label: '我关注的', items: [{ id: 4, object_type: 'task' }], total: 1 },
    mentioned_me: { label: '提到我的', items: [{ id: 5, object_type: 'bug' }], total: 1 },
    project_board: { label: '项目看板', iterations: [{ id: 8 }] }
  })

  assert.deepEqual(viewModel.queueSections.map((section) => section.key), [
    'pending_handling',
    'unassigned',
    'exception_center'
  ])
  assert.equal(viewModel.summaryCards[0].value, 1)
  assert.equal(viewModel.summaryCards[4].value, 1)
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
  assert.deepEqual(unassignedBug.secondary.map((item) => item.key), ['auto_assign_item'])
}

{
  const board = buildProjectBoard([
    {
      id: 9,
      name: 'Iteration A',
      requirements: [{ id: 1, object_type: 'requirement', title: 'Keep me' }],
      tasks: [{ id: 2, object_type: 'task', title: 'Ignore me' }],
      test_cases: [],
      bugs: []
    }
  ], { keyword: 'keep', types: ['requirement'], hideEmpty: true })

  assert.equal(board.length, 1)
  assert.equal(board[0].visibleTotal, 1)
  assert.deepEqual(board[0].groups.map((group) => group.key), ['requirement'])
}

console.log('workbenchViewModel tests passed')
