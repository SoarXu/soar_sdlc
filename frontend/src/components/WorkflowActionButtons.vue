<template>
  <div v-if="visibleActions.length" class="workflow-action-buttons" :class="`workflow-action-buttons-${mode}`">
    <div class="workflow-primary-actions">
      <el-button
        v-for="action in primaryActions"
        :key="action.transition_id"
        :link="mode === 'list'"
        :type="buttonType(action)"
        :loading="submittingAction === action.transition_id"
        @click="openAction(action)"
      >
        {{ action.action_name }}
      </el-button>
    </div>
    <el-dropdown v-if="moreActions.length" trigger="click" @command="handleMoreCommand">
      <el-button :link="mode === 'list'" type="primary" class="workflow-action-more">更多</el-button>
      <template #dropdown>
        <el-dropdown-menu>
          <el-dropdown-item v-for="action in moreActions" :key="action.transition_id" :command="action.transition_id">
            {{ action.action_name }}
          </el-dropdown-item>
        </el-dropdown-menu>
      </template>
    </el-dropdown>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="640px">
      <el-form label-position="top">
        <el-form-item
          v-for="field in formFields"
          :key="field.field"
          :label="field.label || field.field"
          :required="Boolean(field.required)"
        >
          <el-input
            v-if="field.readonly"
            :model-value="formPayload[field.field]"
            disabled
          />
          <el-select
            v-else-if="field.type === 'select'"
            v-model="formPayload[field.field]"
            clearable
            filterable
            :placeholder="field.placeholder || ''"
          >
            <el-option
              v-for="option in fieldOptions(field)"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
          <el-date-picker
            v-else-if="field.type === 'datetime'"
            v-model="formPayload[field.field]"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            :placeholder="field.placeholder || ''"
          />
          <el-date-picker
            v-else-if="field.type === 'date'"
            v-model="formPayload[field.field]"
            type="date"
            value-format="YYYY-MM-DD"
            :placeholder="field.placeholder || ''"
          />
          <el-input
            v-else-if="field.type === 'number'"
            v-model.number="formPayload[field.field]"
            type="number"
            :placeholder="field.placeholder || ''"
          />
          <el-input
            v-else-if="field.type === 'textarea'"
            v-model="formPayload[field.field]"
            type="textarea"
            :rows="field.rows || 4"
            :maxlength="field.max_length"
            :placeholder="field.placeholder || ''"
          />
          <el-input
            v-else
            v-model="formPayload[field.field]"
            :maxlength="field.max_length"
            :placeholder="field.placeholder || ''"
          />
        </el-form-item>

        <el-form-item v-if="needsTargetStateSelection" label="目标状态">
          <el-select
            v-model="selectedTargetStateId"
            clearable
            filterable
            :placeholder="targetStatePlaceholder"
          >
            <el-option
              v-for="option in targetStateOptions"
              :key="option.value"
              :label="option.label"
              :value="option.value"
            />
          </el-select>
        </el-form-item>

        <el-form-item v-if="showOverrideReason" label="覆盖原因">
          <el-input
            v-model="overrideReason"
            type="textarea"
            :rows="2"
            placeholder="手工指定目标状态时可填写"
          />
        </el-form-item>

        <el-alert
          v-if="noActiveTargetIteration"
          title="请先启动迭代"
          type="warning"
          :closable="false"
          show-icon
        />

        <el-alert
          v-if="activeAction?.ui_config?.original_owner_id && activeAction?.ui_config?.original_owner_eligible"
          title="原处理人仍有效，将默认保留"
          type="info"
          :closable="false"
          show-icon
        />
        <el-alert
          v-else-if="hasReactivationOwnerPolicy"
          :title="originalOwnerUnavailableMessage"
          type="warning"
          :closable="false"
          show-icon
        />

        <el-form-item v-if="allowManualOwner" label="下一处理人" :required="reactivationRequiresOwner">
          <el-select v-model="nextOwnerId" clearable filterable :placeholder="ownerSelectionPlaceholder">
            <el-option v-for="user in users" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="代处理原因">
          <el-input v-model="delegateReason" type="textarea" :rows="2" placeholder="仅在管理员或项目负责人代处理时填写" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button :type="buttonType(activeAction)" :loading="Boolean(submittingAction)" :disabled="submitDisabled" @click="submitActiveAction">
          {{ submitText }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="blockerDialogVisible" title="存在未完成事项，无法结束迭代" width="760px">
      <el-alert :title="blockerCountsText" type="warning" :closable="false" show-icon />
      <div class="workflow-blocker-filter">
        <el-segmented v-model="blockerTypeFilter" :options="blockerTypeOptions" />
      </div>
      <el-table :data="blockerRows" border class="workflow-blocker-table">
        <el-table-column label="类型" width="100">
          <template #default="{ row }">{{ blockerTypeLabel(row.object_type) }}</template>
        </el-table-column>
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column label="标题" min-width="220" show-overflow-tooltip>
          <template #default="{ row }">
            <router-link v-if="blockerDetailRoute(row)" class="table-link" :to="blockerDetailRoute(row)">
              {{ row.title }}
            </router-link>
            <span v-else>{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="status_name" label="状态" width="120" />
        <el-table-column prop="owner_id" label="当前处理人 ID" width="130" />
      </el-table>
      <template #footer>
        <el-button type="primary" @click="blockerDialogVisible = false">知道了</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { executeWorkflowTransition, fetchWorkflowTransitions } from '../api/workflowRuntime'
import { fetchUsers } from '../api/users'
import { createWorkItemComment } from '../api/workItemComments'
import { showActionError } from '../utils/actionFeedback'
import { isDelegateReasonRequiredError } from '../utils/permissions'
import {
  actionNeedsConfirmation,
  actionNeedsDialog,
  actionNeedsTargetStateSelection,
  splitListActions,
  workflowCommandType,
  workflowConfirmationMessage
} from '../utils/workflowRuntimeActions'

const props = defineProps({
  objectType: { type: String, required: true },
  objectId: { type: Number, required: true },
  mode: { type: String, default: 'detail' },
  transitions: { type: Array, default: null },
  autoLoad: { type: Boolean, default: true },
  users: { type: Array, default: () => [] }
})

const emit = defineEmits(['command', 'executed', 'loaded'])

const loadedTransitions = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const activeAction = ref(null)
const submittingAction = ref('')
const formPayload = reactive({})
const nextOwnerId = ref(null)
const delegateReason = ref('')
const selectedTargetStateId = ref(null)
const overrideReason = ref('')
const delegateReasonRequired = ref(false)
const loadedUsers = ref([])
const blockerDialogVisible = ref(false)
const blockerDetail = ref({ counts: {}, items: [] })
const blockerTypeFilter = ref('all')

const actions = computed(() => props.transitions ?? loadedTransitions.value)
const listSplit = computed(() => splitListActions(actions.value))
const primaryActions = computed(() => listSplit.value.primaryActions)
const moreActions = computed(() => listSplit.value.moreActions)
const visibleActions = computed(() => [...primaryActions.value, ...moreActions.value])
const formFields = computed(() => activeAction.value?.form_config?.fields || [])
const noActiveTargetIteration = computed(() => {
  const field = formFields.value.find((item) => item.field === 'target_iteration_id')
  return Boolean(field?.required && fieldOptions(field).length === 0)
})
const dialogTitle = computed(() => activeAction.value?.form_config?.title || activeAction.value?.action_name || '执行流转')
const submitText = computed(() => activeAction.value?.form_config?.submit_text || activeAction.value?.action_name || '确认')
const allowManualOwner = computed(() => actionAllowsManualOwner(activeAction.value))
const hasReactivationOwnerPolicy = computed(() => (
  Object.prototype.hasOwnProperty.call(activeAction.value?.ui_config || {}, 'allow_unassigned')
))
const reactivationAllowsUnassigned = computed(() => activeAction.value?.ui_config?.allow_unassigned === true)
const reactivationRequiresOwner = computed(() => (
  allowManualOwner.value && hasReactivationOwnerPolicy.value && !reactivationAllowsUnassigned.value
))
const missingRequiredOwner = computed(() => (
  reactivationRequiresOwner.value
    && (nextOwnerId.value === null || nextOwnerId.value === undefined || nextOwnerId.value === '')
))
const submitDisabled = computed(() => noActiveTargetIteration.value || missingRequiredOwner.value)
const originalOwnerUnavailableMessage = computed(() => {
  const reason = activeAction.value?.ui_config?.original_owner_unavailable_reason?.message
  if (reactivationAllowsUnassigned.value) {
    return reason ? `${reason}，可重新选择处理人，也可保持未分派` : '可选择处理人，也可保持未分派'
  }
  return reason ? `${reason}，请选择处理人` : '请选择处理人'
})
const ownerSelectionPlaceholder = computed(() => (
  reactivationRequiresOwner.value ? '请选择处理人' : '可保持未分派'
))
const needsTargetStateSelection = computed(() => actionNeedsTargetStateSelection(activeAction.value))
const showOverrideReason = computed(() => needsTargetStateSelection.value && Boolean(selectedTargetStateId.value))
const targetStateOptions = computed(() => {
  const states = activeAction.value?.allowed_target_states || []
  return states.map((state) => ({ label: state.status_name, value: state.id }))
})
const targetStatePlaceholder = computed(() => (
  activeAction.value?.routing_mode === 'manual_allowed'
    ? '请选择目标状态'
    : '默认按规则自动流转，可按需覆盖'
))
const users = computed(() => props.users.length ? props.users : loadedUsers.value)
const blockerCountsText = computed(() => {
  const counts = blockerDetail.value?.counts || {}
  return `需求 ${counts.requirement || 0} 项，任务 ${counts.task || 0} 项，Bug ${counts.bug || 0} 项，测试单 ${counts.test_run || 0} 项`
})
const blockerTypeOptions = computed(() => {
  const rows = blockerDetail.value?.items || []
  return [
    { label: `全部 ${rows.length}`, value: 'all' },
    ...['requirement', 'task', 'bug', 'test_run']
      .map((value) => ({
        label: `${blockerTypeLabel(value)} ${rows.filter((row) => row.object_type === value).length}`,
        value
      }))
      .filter((option) => option.label.endsWith(' 0') === false)
  ]
})
const blockerRows = computed(() => {
  const rows = blockerDetail.value?.items || []
  return blockerTypeFilter.value === 'all'
    ? rows
    : rows.filter((row) => row.object_type === blockerTypeFilter.value)
})

function blockerTypeLabel(value) {
  return { requirement: '需求', task: '任务', bug: 'Bug', test_run: '测试单' }[value] || value
}

function blockerDetailRoute(row) {
  const routeName = {
    requirement: 'requirement-detail',
    task: 'task-detail',
    bug: 'bug-detail'
  }[row.object_type]
  return routeName ? { name: routeName, params: { id: row.id } } : null
}

function buttonType(action) {
  return action?.button_type || action?.ui_config?.button_type || 'primary'
}

function actionAllowsManualOwner(action) {
  return Boolean(action?.form_config?.allow_manual_owner || action?.ui_config?.allow_manual_owner)
}

function fieldOptions(field) {
  const options = field.options || []
  return options.map((option) => {
    if (typeof option === 'string' || typeof option === 'number') {
      return { label: String(option), value: option }
    }
    return { label: option.label ?? option.value, value: option.value }
  })
}

function resetForm(action) {
  Object.keys(formPayload).forEach((key) => delete formPayload[key])
  for (const field of action?.form_config?.fields || []) {
    formPayload[field.field] = field.default_value ?? null
  }
  nextOwnerId.value = action?.ui_config?.recommended_owner_id
    ?? action?.ui_config?.resolved_default_owner_id
    ?? null
  delegateReason.value = ''
  selectedTargetStateId.value = null
  overrideReason.value = ''
  delegateReasonRequired.value = false
}

async function ensureUsersLoaded() {
  if (props.users.length || loadedUsers.value.length || !allowManualOwner.value) return
  const { data } = await fetchUsers()
  loadedUsers.value = data
}

async function openAction(action) {
  activeAction.value = action
  resetForm(action)
  const commandType = workflowCommandType(action)
  if (commandType && commandType !== 'add_information') {
    emit('command', { commandType, action })
    return
  }
  await ensureUsersLoaded()
  if (actionNeedsDialog(action)) {
    dialogVisible.value = true
    return
  }
  if (actionNeedsConfirmation(action)) {
    await ElMessageBox.confirm(workflowConfirmationMessage(action), '提示', {
      type: buttonType(action),
      confirmButtonText: '确认',
      cancelButtonText: '取消'
    })
  }
  await submitAction(action)
}

function handleMoreCommand(transitionId) {
  const action = moreActions.value.find((item) => item.transition_id === transitionId)
  if (action) openAction(action)
}

function validatePayload() {
  if (delegateReasonRequired.value && !delegateReason.value.trim()) {
    ElMessage.warning('请填写代处理原因')
    return false
  }
  if (activeAction.value?.routing_mode === 'manual_allowed' && !selectedTargetStateId.value) {
    ElMessage.warning('请选择目标状态')
    return false
  }
  if (missingRequiredOwner.value) {
    ElMessage.warning('请选择处理人')
    return false
  }
  for (const field of formFields.value) {
    if (!field.required) continue
    const value = formPayload[field.field]
    if (value === null || value === undefined || value === '') {
      ElMessage.warning(`请填写${field.label || field.field}`)
      return false
    }
  }
  return true
}

async function submitActiveAction() {
  if (!activeAction.value || !validatePayload()) return
  await submitAction(activeAction.value)
}

async function submitAction(action) {
  submittingAction.value = action.transition_id
  try {
    if (workflowCommandType(action) === 'add_information') {
      await createWorkItemComment({
        object_type: props.objectType,
        object_id: props.objectId,
        body: String(formPayload.content || '').trim(),
        mentioned_user_ids: []
      })
      dialogVisible.value = false
      ElMessage.success('补充信息成功')
      emit('executed', { command_type: 'add_information' })
      return
    }
    const payload = {
      transition_id: action.transition_id,
      payload: Object.fromEntries(
        formFields.value.filter((field) => !field.readonly).map((field) => [field.field, formPayload[field.field]])
      )
    }
    if (nextOwnerId.value) payload.next_owner_id = nextOwnerId.value
    if (delegateReason.value.trim()) payload.delegate_reason = delegateReason.value.trim()
    if (selectedTargetStateId.value) payload.selected_target_state_id = selectedTargetStateId.value
    if (overrideReason.value.trim()) payload.override_reason = overrideReason.value.trim()
    const { data } = await executeWorkflowTransition(props.objectType, props.objectId, payload)
    dialogVisible.value = false
    ElMessage.success(`${action.action_name}成功`)
    emit('executed', data)
    if (props.autoLoad && props.objectId) await loadTransitions()
  } catch (error) {
    const detail = error?.response?.data?.detail
    if (detail?.code === 'ITERATION_HAS_OPEN_ITEMS') {
      blockerDetail.value = detail
      blockerTypeFilter.value = 'all'
      dialogVisible.value = false
      blockerDialogVisible.value = true
      return
    }
    if (isDelegateReasonRequiredError(error)) {
      activeAction.value = action
      delegateReasonRequired.value = true
      dialogVisible.value = true
      ElMessage.warning('请填写代处理原因')
      return
    }
    showActionError(error, `${action.action_name}失败`)
  } finally {
    submittingAction.value = ''
  }
}

async function loadTransitions() {
  if (!props.autoLoad || !props.objectType || !props.objectId || props.transitions) return
  loading.value = true
  try {
    const { data } = await fetchWorkflowTransitions(props.objectType, props.objectId)
    loadedTransitions.value = data
    emit('loaded', data)
  } catch {
    loadedTransitions.value = []
  } finally {
    loading.value = false
  }
}

watch(() => [props.objectType, props.objectId], loadTransitions)
onMounted(loadTransitions)
</script>

<style scoped>
.workflow-action-buttons,
.workflow-primary-actions {
  display: inline-flex;
  align-items: center;
  flex-wrap: nowrap;
  white-space: nowrap;
}

.workflow-action-buttons {
  gap: 8px;
}

.workflow-primary-actions {
  gap: 4px;
}

.workflow-blocker-filter {
  margin: 16px 0 12px;
}
</style>
