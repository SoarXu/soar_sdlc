import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

const source = await readFile(new URL('./WorkflowActionButtons.vue', import.meta.url), 'utf8')

assert.match(source, /actionNeedsConfirmation/)
assert.match(source, /workflowConfirmationMessage/)
assert.match(
  source,
  /<div v-if="primaryActions\.length" class="workflow-primary-actions">/,
  'an empty primary action group must not indent the more-actions dropdown'
)
assert.match(
  source,
  /<el-dialog[^>]*\bappend-to-body\b/,
  'workflow dialogs must escape fixed table-cell stacking contexts'
)
assert.match(
  source,
  /<el-form-item v-if="delegateReasonRequired" label="代处理原因" required>/,
  'delegate reason must only appear after the runtime confirms delegated execution'
)
assert.match(source, /<slot name="after-primary" \/>/)
assert.match(source, /eligibleAssigneeUsers/)
assert.match(source, /activeAction\.value\?\.eligible_assignee_ids/)
assert.match(source, /v-for="user in eligibleAssigneeUsers"/)
assert.doesNotMatch(source, /v-for="user in users"/)
assert.ok(
  source.indexOf('<slot name="after-primary" />') < source.indexOf('<el-dropdown v-if="moreActions.length"'),
  'page actions inserted after primary workflow actions must stay before the more menu'
)

const submitBlock = source.slice(
  source.indexOf('async function submitActiveAction'),
  source.indexOf('async function submitAction')
)

assert.doesNotMatch(submitBlock, /ElMessageBox\.confirm/)
assert.doesNotMatch(source, /ui_config\?\.confirm_message/)
assert.doesNotMatch(source, /ui_config\?\.confirm_title/)
assert.match(source, /recommended_owner_id/)
assert.match(source, /resolved_default_owner_id/)
assert.match(source, /original_owner_unavailable_reason/)
assert.match(source, /originalOwnerUnavailableMessage/)
assert.match(source, /reactivationAllowsUnassigned/)
assert.match(source, /reactivationRequiresOwner/)
assert.match(source, /missingRequiredOwner/)
assert.match(source, /submitDisabled/)
assert.match(source, /field\.readonly/)
assert.match(source, /noActiveTargetIteration/)
assert.match(source, /请先启动迭代/)
assert.match(source, /:disabled="submitDisabled"/)
assert.match(source, /原处理人仍有效，将默认保留/)
assert.match(source, /请选择处理人/)
assert.match(source, /可保持未分派/)
assert.match(source, /ITERATION_HAS_OPEN_ITEMS/)
assert.match(source, /blockerDetail/)
assert.match(source, /blockerTypeFilter/)
assert.match(source, /blockerRows/)
assert.match(source, /blockerDetailRoute\(row\)/)
assert.match(source, /存在未完成事项，无法结束迭代/)

const blockerDialogStart = source.indexOf('<el-dialog v-model="blockerDialogVisible"')
const blockerDialogEnd = source.indexOf('</el-dialog>', blockerDialogStart)
assert.notEqual(blockerDialogStart, -1)
assert.notEqual(blockerDialogEnd, -1)
assert.match(
  source.slice(blockerDialogStart, blockerDialogEnd),
  /\bappend-to-body\b/,
  'the iteration blocker dialog must escape table stacking contexts'
)

const workflowSubmitBlock = source.slice(
  source.indexOf('async function submitAction'),
  source.indexOf('async function loadTransitions')
)

assert.match(
  source,
  /function isUnfinishedProjectIterationBlocker\(error\) \{[\s\S]*?props\.objectType === 'project'[\s\S]*?PROJECT_HAS_UNFINISHED_ITEMS/,
  'Project-close iteration blockers must be recognized before generic action feedback'
)
assert.match(
  workflowSubmitBlock,
  /if \(isUnfinishedProjectIterationBlocker\(error\)\) \{\s*ElMessage\.warning\('项目存在未结束迭代，无法关闭。'\)\s*return\s*\}/,
  'Project-close iteration blockers must use an automatically dismissed Chinese warning message'
)
const iterationBlockerStart = workflowSubmitBlock.indexOf('if (isUnfinishedProjectIterationBlocker(error))')
const delegateReasonCheckStart = workflowSubmitBlock.indexOf('if (isDelegateReasonRequiredError(error))')
assert.doesNotMatch(
  workflowSubmitBlock.slice(iterationBlockerStart, delegateReasonCheckStart),
  /showActionError/,
  'The iteration blocker branch must not open the generic modal error dialog'
)

console.log('workflow action button behavior tests passed')
