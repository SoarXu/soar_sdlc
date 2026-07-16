<template>
  <div v-if="visibleActions.length" class="workflow-action-buttons" :class="`workflow-action-buttons-${mode}`">
    <template v-if="mode === 'list'">
      <el-button
        v-if="primaryAction"
        link
        :type="buttonType(primaryAction)"
        :loading="submittingAction === primaryAction.action_key"
        @click="openAction(primaryAction)"
      >
        {{ primaryAction.action_name }}
      </el-button>
      <el-dropdown v-if="moreActions.length" trigger="click" @command="handleMoreCommand">
        <el-button link type="primary" class="workflow-action-more">更多</el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item v-for="action in moreActions" :key="action.action_key" :command="action.action_key">
              {{ action.action_name }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </template>

    <template v-else>
      <el-button
        v-for="action in visibleActions"
        :key="action.action_key"
        :type="buttonType(action)"
        :loading="submittingAction === action.action_key"
        @click="openAction(action)"
      >
        {{ action.action_name }}
      </el-button>
    </template>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="640px">
      <el-form label-position="top">
        <el-form-item
          v-for="field in formFields"
          :key="field.field"
          :label="field.label || field.field"
          :required="Boolean(field.required)"
        >
          <el-select
            v-if="field.type === 'select'"
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

        <el-form-item v-if="needsTargetStatusSelection" label="目标状态">
          <el-select
            v-model="selectedTargetStatus"
            clearable
            filterable
            :placeholder="targetStatusPlaceholder"
          >
            <el-option
              v-for="option in targetStatusOptions"
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

        <el-form-item v-if="allowManualOwner" label="下一处理人">
          <el-select v-model="nextOwnerId" clearable filterable placeholder="不指定则按规则自动分配">
            <el-option v-for="user in users" :key="user.id" :label="user.full_name || user.username" :value="user.id" />
          </el-select>
        </el-form-item>

        <el-form-item label="代处理原因">
          <el-input v-model="delegateReason" type="textarea" :rows="2" placeholder="仅在管理员或项目负责人代处理时填写" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button :type="buttonType(activeAction)" :loading="Boolean(submittingAction)" @click="submitActiveAction">
          {{ submitText }}
        </el-button>
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
  actionNeedsDialog,
  actionNeedsTargetStatusSelection,
  sortWorkflowActions,
  splitListActions,
  visibleDetailActions,
  workflowCommandType
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
const selectedTargetStatus = ref('')
const overrideReason = ref('')
const delegateReasonRequired = ref(false)
const loadedUsers = ref([])

const actions = computed(() => props.transitions ?? loadedTransitions.value)
const visibleActions = computed(() => {
  if (props.mode === 'list') return sortWorkflowActions(actions.value)
  return visibleDetailActions(actions.value)
})
const listSplit = computed(() => splitListActions(actions.value))
const primaryAction = computed(() => listSplit.value.primaryAction)
const moreActions = computed(() => listSplit.value.moreActions)
const formFields = computed(() => activeAction.value?.form_config?.fields || [])
const dialogTitle = computed(() => activeAction.value?.form_config?.title || activeAction.value?.action_name || '执行流转')
const submitText = computed(() => activeAction.value?.form_config?.submit_text || activeAction.value?.action_name || '确认')
const allowManualOwner = computed(() => actionAllowsManualOwner(activeAction.value))
const needsTargetStatusSelection = computed(() => actionNeedsTargetStatusSelection(activeAction.value))
const showOverrideReason = computed(() => needsTargetStatusSelection.value && Boolean(selectedTargetStatus.value))
const targetStatusOptions = computed(() => {
  const statuses = activeAction.value?.allowed_target_statuses || []
  return statuses.map((status) => ({ label: formatStatusLabel(status), value: status }))
})
const targetStatusPlaceholder = computed(() => (
  activeAction.value?.routing_mode === 'manual_allowed'
    ? '请选择目标状态'
    : '默认按规则自动流转，可按需覆盖'
))
const users = computed(() => props.users.length ? props.users : loadedUsers.value)

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

function formatStatusLabel(status) {
  return String(status || '')
    .split('_')
    .filter(Boolean)
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(' ')
}

function resetForm(action) {
  Object.keys(formPayload).forEach((key) => delete formPayload[key])
  for (const field of action?.form_config?.fields || []) {
    formPayload[field.field] = field.default_value ?? null
  }
  nextOwnerId.value = null
  delegateReason.value = ''
  selectedTargetStatus.value = ''
  overrideReason.value = ''
  delegateReasonRequired.value = false
}

function confirmMessage(action) {
  return action?.ui_config?.confirm_message || `确认执行「${action?.action_name || action?.action_key}」？`
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
  if (action.confirm_required) {
    await ElMessageBox.confirm(confirmMessage(action), action?.ui_config?.confirm_title || action.action_name, { type: buttonType(action) })
  }
  await submitAction(action)
}

function handleMoreCommand(actionKey) {
  const action = moreActions.value.find((item) => item.action_key === actionKey)
  if (action) openAction(action)
}

function validatePayload() {
  if (delegateReasonRequired.value && !delegateReason.value.trim()) {
    ElMessage.warning('请填写代处理原因')
    return false
  }
  if (activeAction.value?.routing_mode === 'manual_allowed' && !selectedTargetStatus.value) {
    ElMessage.warning('请选择目标状态')
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
  if (activeAction.value.confirm_required) {
    await ElMessageBox.confirm(confirmMessage(activeAction.value), activeAction.value?.ui_config?.confirm_title || activeAction.value.action_name, { type: buttonType(activeAction.value) })
  }
  await submitAction(activeAction.value)
}

async function submitAction(action) {
  submittingAction.value = action.action_key
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
      action_key: action.action_key,
      payload: { ...formPayload }
    }
    if (nextOwnerId.value) payload.next_owner_id = nextOwnerId.value
    if (delegateReason.value.trim()) payload.delegate_reason = delegateReason.value.trim()
    if (selectedTargetStatus.value) payload.selected_target_status = selectedTargetStatus.value
    if (overrideReason.value.trim()) payload.override_reason = overrideReason.value.trim()
    const { data } = await executeWorkflowTransition(props.objectType, props.objectId, payload)
    dialogVisible.value = false
    ElMessage.success(`${action.action_name}成功`)
    emit('executed', data)
    if (props.autoLoad && props.objectId) await loadTransitions()
  } catch (error) {
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
