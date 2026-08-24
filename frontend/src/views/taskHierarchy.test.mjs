import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const taskDetail = await readFile(new URL('./TaskDetailView.vue', import.meta.url), 'utf8')
const workflowButtons = await readFile(new URL('../components/WorkflowActionButtons.vue', import.meta.url), 'utf8')

assert.match(taskDetail, /fetchTaskChildren/)
assert.match(taskDetail, /fetchProjectMembers/)
assert.match(taskDetail, /canCreateChildTask/)
assert.match(taskDetail, /parent_task/)
assert.match(taskDetail, /父任务/)
assert.match(taskDetail, /子任务/)
assert.match(taskDetail, /childTasks/)
assert.match(taskDetail, /childTaskDialogVisible/)
assert.match(taskDetail, /parent_task_id: task.value.id/)
assert.match(taskDetail, /readonly/)
assert.match(taskDetail, /childTaskPage/)
assert.match(taskDetail, /loadTaskChildren/)

assert.match(workflowButtons, /TASK_DESCENDANTS_NOT_TERMINAL/)
assert.match(workflowButtons, /存在未结束子任务，无法结束任务/)
assert.match(workflowButtons, /TASK_DESCENDANTS_NOT_TERMINAL' \? 'task'/)

console.log('task hierarchy detail behavior tests passed')
