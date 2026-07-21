<template>
  <el-drawer
    class="workflow-advanced-drawer"
    v-model="drawerVisible"
    direction="rtl"
    :size="drawerSize"
    :before-close="requestClose"
    :append-to-body="false"
    :lock-scroll="false"
    modal-class="workflow-advanced-drawer-modal"
  >
    <template #header>
      <div class="drawer-header">
        <el-button v-if="transition" text circle aria-label="返回流转列表" @click="requestBack">
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
        <div>
          <h2>{{ transition?.action_name || state?.status_name || '流转配置' }}</h2>
          <p v-if="transition">{{ stateName(transition.from_state_id) }} -&gt; {{ stateName(transition.to_state_id) }}</p>
          <p v-else>配置该状态可以执行的流转动作</p>
        </div>
        <span v-if="hasPendingChanges()" class="draft-status">未应用修改</span>
      </div>
    </template>

    <div v-if="state && !transition" class="state-action-shell">
      <div class="state-settings">
        <el-form label-position="top">
          <div class="form-grid">
            <el-form-item label="状态名称"><el-input v-model="state.status_name" /></el-form-item>
            <el-form-item label="状态类型">
              <el-select v-model="state.category">
                <el-option label="开始" value="start" />
                <el-option label="普通" value="normal" />
                <el-option label="结束" value="terminal" />
              </el-select>
            </el-form-item>
            <el-form-item label="颜色"><el-color-picker v-model="state.color" /></el-form-item>
            <el-form-item label="启用"><el-switch v-model="state.enabled" /></el-form-item>
          </div>
        </el-form>
      </div>
      <section v-for="group in actionGroups" :key="group.key" class="action-group">
        <header class="action-group-header">
          <div><h3>{{ group.label }}</h3><span>{{ groupedTransitions[group.key].length }}</span></div>
          <el-tooltip content="新增流转" placement="top">
            <el-button text circle :aria-label="`在${group.label}新增流转`" @click="emit('add-transition', group.key)">
              <el-icon><Plus /></el-icon>
            </el-button>
          </el-tooltip>
        </header>
        <div
          class="action-drop-zone"
          @dragover.prevent
          @drop.prevent="dropTransition(group.key, groupedTransitions[group.key].length)"
        >
          <button
            v-for="(item, index) in groupedTransitions[group.key]"
            :key="transitionIdentity(item)"
            class="transition-card"
            type="button"
            draggable="true"
            @dragstart="startTransitionDrag(item)"
            @dragover.prevent
            @drop.stop.prevent="dropTransition(group.key, index)"
            @click="emit('select-transition', item)"
          >
            <el-icon class="drag-handle"><Rank /></el-icon>
            <span class="transition-card-copy">
              <strong>{{ item.action_name }}</strong>
              <small>到 {{ stateName(item.to_state_id) }}</small>
            </span>
          </button>
          <el-empty v-if="!groupedTransitions[group.key].length" :description="`${group.label}暂无流转`" :image-size="48" />
        </div>
      </section>
    </div>

    <div v-else-if="draft" class="drawer-shell">
      <div class="drawer-layout">
        <nav class="section-nav" aria-label="高级配置分区">
          <button
            v-for="section in sections"
            :key="section.key"
            class="section-nav-item"
            :class="{ active: activeSection === section.key }"
            type="button"
            @click="activeSection = section.key"
          >
            <span class="section-indicator" :class="sectionStates[section.key]" aria-hidden="true" />
            <span>{{ section.label }}</span>
          </button>
        </nav>

        <main class="section-content">
          <section v-if="activeSection === 'basic'" class="editor-section">
            <div class="section-heading"><h3>基础配置</h3></div>
            <div class="form-grid">
              <el-form-item label="流转名称"><el-input v-model="transition.action_name" /></el-form-item>
              <el-form-item label="来源状态"><el-input :model-value="stateName(transition.from_state_id)" disabled /></el-form-item>
              <el-form-item label="目标状态">
                <el-select v-model="transition.to_state_id">
                  <el-option v-for="item in states" :key="item.id" :label="item.status_name" :value="item.id" />
                </el-select>
              </el-form-item>
              <el-form-item label="启用"><el-switch v-model="transition.enabled" /></el-form-item>
            </div>
            <div class="diagram-routing-row">
              <div>
                <span>画布布线</span>
                <strong>{{ isManualDiagramRoute(transition.diagram_config) ? '手工布线' : '自动布线' }}</strong>
              </div>
              <el-button v-if="isManualDiagramRoute(transition.diagram_config)" type="primary" link @click="resetDiagramRoute">
                恢复自动布线
              </el-button>
            </div>
            <el-button v-if="!transition.id" type="danger" plain @click="emit('remove-transition')">删除未保存流转</el-button>
          </section>

          <section v-else-if="activeSection === 'rules'" class="editor-section">
            <div class="section-heading">
              <h3>流转规则</h3>
              <p>配置字段路由、覆盖权限和流转门禁。</p>
            </div>
            <div class="form-grid">
              <el-form-item label="条件字段" :error="errorFor('condition_config.field')">
                <el-input v-model="draft.condition_config.field" placeholder="动作表单字段键" />
              </el-form-item>
              <el-form-item label="路由模式">
                <el-select v-model="draft.condition_config.routing_mode">
                  <el-option v-for="option in routingModeOptions" :key="option.value" v-bind="option" />
                </el-select>
              </el-form-item>
              <el-form-item
                v-if="draft.condition_config.routing_mode === 'automatic_with_override'"
                class="full-width"
                label="允许覆盖角色"
                :error="errorFor('condition_config.allow_override_roles')"
              >
                <el-select
                  v-model="draft.condition_config.allow_override_roles"
                  multiple
                  collapse-tags
                  collapse-tags-tooltip
                  :max-collapse-tags="2"
                >
                  <el-option v-for="option in roleOptions" :key="option.value" v-bind="option" />
                </el-select>
              </el-form-item>
              <el-form-item label="流转门禁">
                <el-select v-model="validatorType" clearable placeholder="不启用">
                  <el-option v-for="option in validatorOptions" :key="option.value" v-bind="option" />
                </el-select>
              </el-form-item>
            </div>

            <el-alert
              v-if="draft.condition_config.route_dictionary === 'bug_type'"
              title="Bug 类型字典自动路由"
              type="info"
              :closable="false"
              show-icon
            />
            <template v-else>
              <div class="subsection-heading">
                <h4>静态路由</h4>
                <el-button type="primary" link @click="addRoute">新增路由</el-button>
              </div>
              <div v-if="!draft.condition_routes.length" class="empty-hint">尚未配置静态路由。</div>
              <div v-for="(route, index) in draft.condition_routes" :key="index" class="route-row">
                <el-form-item label="字段值" :error="errorFor(`condition_routes.${index}.value`)">
                  <el-input v-model="route.value" />
                </el-form-item>
                <el-form-item label="目标状态" :error="errorFor(`condition_routes.${index}.state_id`)">
                  <el-select v-model="route.state_id">
                    <el-option
                      v-for="state in states"
                      :key="state.id"
                      :label="state.status_name"
                      :value="state.id"
                    />
                  </el-select>
                </el-form-item>
                <el-button class="row-remove" type="danger" text @click="removeRoute(index)">删除</el-button>
              </div>
            </template>
          </section>

          <section v-else-if="activeSection === 'assignment'" class="editor-section">
            <div class="section-heading">
              <h3>处理人与权限</h3>
              <p>允许执行角色和流转后的处理人来源分别配置。</p>
            </div>
            <div class="form-grid">
              <el-form-item class="full-width" label="允许执行角色">
                <el-select
                  v-model="draft.allowed_role_list"
                  multiple
                  collapse-tags
                  collapse-tags-tooltip
                  :max-collapse-tags="2"
                >
                  <el-option v-for="option in roleOptions" :key="option.value" v-bind="option" />
                </el-select>
              </el-form-item>
              <el-form-item label="主要处理人来源">
                <el-select v-model="draft.handler_rule.target_type">
                  <el-option v-for="option in targetTypes" :key="option.value" v-bind="option" />
                </el-select>
              </el-form-item>
              <el-form-item label="回退处理人来源">
                <el-select v-model="draft.handler_rule.fallback_type">
                  <el-option v-for="option in targetTypes" :key="option.value" v-bind="option" />
                </el-select>
              </el-form-item>
              <el-form-item
                v-if="draft.handler_rule.target_type === 'project_role'"
                label="主要目标角色"
                :error="errorFor('handler_target_roles')"
              >
                <el-select
                  v-model="draft.handler_target_roles"
                  multiple
                  collapse-tags
                  collapse-tags-tooltip
                  :max-collapse-tags="2"
                >
                  <el-option v-for="option in roleOptions" :key="option.value" v-bind="option" />
                </el-select>
              </el-form-item>
              <el-form-item
                v-if="draft.handler_rule.fallback_type === 'project_role'"
                label="回退目标角色"
                :error="errorFor('handler_fallback_roles')"
              >
                <el-select
                  v-model="draft.handler_fallback_roles"
                  multiple
                  collapse-tags
                  collapse-tags-tooltip
                  :max-collapse-tags="2"
                >
                  <el-option v-for="option in roleOptions" :key="option.value" v-bind="option" />
                </el-select>
              </el-form-item>
              <el-form-item class="full-width" label="手动指定处理人">
                <el-switch v-model="draft.handler_rule.allow_manual_owner" active-text="允许" inactive-text="不允许" />
              </el-form-item>
            </div>
          </section>

          <section v-else-if="activeSection === 'form'" class="editor-section">
            <div class="section-heading">
              <h3>系统固定动作表单</h3>
            </div>
            <div class="form-grid">
              <el-form-item label="表单类型">
                <el-select v-model="formPreset">
                  <el-option v-for="option in formPresetOptions" :key="option.value" v-bind="option" />
                </el-select>
              </el-form-item>
            </div>
            <div v-if="draft.form_config.fields.length" class="fixed-form-preview">
              <div v-for="field in draft.form_config.fields" :key="field.field">
                <strong>{{ field.label }}</strong>
                <span>{{ field.required ? '必填' : '选填' }}</span>
              </div>
            </div>
          </section>

          <section v-else-if="activeSection === 'button'" class="editor-section">
            <div class="section-heading">
              <h3>按钮展示</h3>
              <p>控制动作在列表和详情页中的展示方式。</p>
            </div>
            <div class="form-grid">
              <el-form-item label="按钮样式">
                <el-select v-model="draft.ui_config.button_type">
                  <el-option v-for="option in buttonTypeOptions" :key="option.value" v-bind="option" />
                </el-select>
              </el-form-item>
              <el-form-item label="列表位置">
                <el-select v-model="draft.ui_config.list_display">
                  <el-option v-for="option in listDisplayOptions" :key="option.value" v-bind="option" />
                </el-select>
              </el-form-item>
              <el-form-item label="动作类别">
                <el-select v-model="draft.ui_config.action_category" clearable>
                  <el-option v-for="option in actionCategoryOptions" :key="option.value" v-bind="option" />
                </el-select>
              </el-form-item>
              <el-form-item label="执行前确认"><el-switch v-model="draft.ui_config.confirm_required" /></el-form-item>
            </div>
          </section>

          <section v-else class="editor-section">
            <div class="section-heading">
              <h3>通知</h3>
              <p>只配置系统站内通知，不增加新的通知渠道。</p>
            </div>
            <div class="notification-block">
              <div class="notification-heading">
                <h4>执行前通知</h4>
                <el-switch :model-value="Boolean(draft.trigger_config)" @update:model-value="toggleNotification('trigger_config', $event)" />
              </div>
              <div v-if="draft.trigger_config" class="form-grid">
                <el-form-item label="接收人" :error="errorFor('trigger_config.receiver')">
                  <el-select v-model="draft.trigger_config.receiver">
                    <el-option v-for="option in receiverOptions" :key="option.value" v-bind="option" />
                  </el-select>
                </el-form-item>
                <el-form-item label="通知标题" :error="errorFor('trigger_config.title')">
                  <el-input v-model="draft.trigger_config.title" />
                </el-form-item>
              </div>
            </div>
            <div class="notification-block">
              <div class="notification-heading">
                <h4>完成后通知</h4>
                <el-switch :model-value="Boolean(draft.post_action_config)" @update:model-value="toggleNotification('post_action_config', $event)" />
              </div>
              <div v-if="draft.post_action_config" class="form-grid">
                <el-form-item label="接收人" :error="errorFor('post_action_config.receiver')">
                  <el-select v-model="draft.post_action_config.receiver">
                    <el-option v-for="option in receiverOptions" :key="option.value" v-bind="option" />
                  </el-select>
                </el-form-item>
                <el-form-item label="通知标题" :error="errorFor('post_action_config.title')">
                  <el-input v-model="draft.post_action_config.title" />
                </el-form-item>
              </div>
            </div>
          </section>
        </main>
      </div>

      <footer class="drawer-footer">
        <el-button @click="clearActiveSection">清空本页配置</el-button>
        <div class="footer-actions">
          <el-button @click="cancel">取消</el-button>
          <el-button type="primary" @click="apply">应用配置</el-button>
        </div>
      </footer>
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { ArrowLeft, Plus, Rank } from '@element-plus/icons-vue'

import {
  ADVANCED_SECTION_KEYS,
  advancedSectionStates,
  clearAdvancedSection,
  createAdvancedConfigDraft,
  isAdvancedConfigDirty,
  validateAdvancedConfig
} from '../utils/workflowAdvancedConfig'
import { groupStateTransitions } from '../utils/workflowTransitionOrdering'
import { isManualDiagramRoute } from '../utils/workflowManualRoute'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  state: { type: Object, default: null },
  transition: { type: Object, default: null },
  transitions: { type: Array, default: () => [] },
  states: { type: Array, default: () => [] },
  roleOptions: { type: Array, default: () => [] },
  targetTypes: { type: Array, default: () => [] }
})

const emit = defineEmits([
  'update:modelValue', 'apply', 'back', 'select-transition', 'move-transition',
  'add-transition', 'remove-transition', 'reset-diagram-route'
])

const drawerSize = 'clamp(520px, 42vw, 640px)'
const sections = [
  { key: 'basic', label: '基础配置' },
  { key: 'rules', label: '流转规则' },
  { key: 'assignment', label: '处理人与权限' },
  { key: 'form', label: '动作表单' },
  { key: 'button', label: '按钮展示' },
  { key: 'notification', label: '通知' }
]
const routingModeOptions = [
  { label: '自动路由', value: 'automatic' },
  { label: '手动选择', value: 'manual_allowed' },
  { label: '自动并允许覆盖', value: 'automatic_with_override' }
]
const validatorOptions = [
  { label: 'Bug 关联任务完成门禁', value: 'bug_close_gate' },
  { label: '需求关联项完成门禁', value: 'requirement_terminal_gate' },
  { label: '迭代工作项完成门禁', value: 'iteration_terminal_gate' },
  { label: '项目工作项完成门禁', value: 'project_close_gate' }
]
const formPresetOptions = [
  { label: '无需填写', value: 'none' },
  { label: '必填原因', value: 'required_reason' },
  { label: '可选原因', value: 'optional_reason' },
  { label: 'Bug 类型选择', value: 'bug_type' },
  { label: 'Bug 类型重分类及原因', value: 'bug_reclassify' },
  { label: '补充信息', value: 'information' },
  { label: '实际开始日期', value: 'actual_start_date' },
  { label: '实际完成日期', value: 'actual_end_date' }
]
const buttonTypeOptions = [
  { label: '主要', value: 'primary' },
  { label: '成功', value: 'success' },
  { label: '警告', value: 'warning' },
  { label: '危险', value: 'danger' },
  { label: '普通', value: 'info' }
]
const listDisplayOptions = [
  { label: '主操作', value: 'primary' },
  { label: '更多操作', value: 'more' }
]
const actionCategoryOptions = [
  { label: '流程', value: 'workflow' },
  { label: '管理', value: 'management' },
  { label: '信息', value: 'information' },
  { label: '导航', value: 'navigation' }
]
const receiverOptions = [
  { label: '当前操作人', value: 'actor' },
  { label: '当前处理人', value: 'current_handler' },
  { label: '下一处理人', value: 'next_handler' },
  { label: '创建人', value: 'creator' },
  { label: '项目负责人', value: 'project_owner' }
]

const draft = ref(null)
const activeSection = ref('basic')
const errors = ref(createErrors())
const drawerVisible = ref(false)
const draggedTransitionIdentity = ref(null)
const actionGroups = [
  { key: 'primary', label: '主操作' },
  { key: 'more', label: '更多操作' }
]
const groupedTransitions = computed(() => groupStateTransitions(props.transitions, props.state?.id))

const sectionStates = computed(() => (
  draft.value ? advancedSectionStates(draft.value, props.states) : unconfiguredSectionStates()
))
const validatorType = computed({
  get: () => draft.value?.validator_config?.type || '',
  set: (value) => {
    if (!draft.value) return
    draft.value.validator_config = value ? { ...draft.value.validator_config, type: value } : null
  }
})

watch(() => props.modelValue, (visible, wasVisible) => {
  if (visible !== drawerVisible.value) drawerVisible.value = visible
  if (visible && !wasVisible) initializeDraft()
}, { immediate: true })

watch(() => props.transition, () => {
  if (drawerVisible.value) initializeDraft()
})
const formPreset = computed({
  get: () => formPresetKey(draft.value?.form_config?.fields || []),
  set: (value) => {
    if (!draft.value) return
    draft.value.form_config = fixedFormConfig(value)
  }
})

watch(drawerVisible, (visible) => {
  if (visible !== props.modelValue) emit('update:modelValue', visible)
})

function createErrors() {
  return Object.fromEntries(ADVANCED_SECTION_KEYS.map((section) => [section, []]))
}

function unconfiguredSectionStates() {
  return Object.fromEntries(ADVANCED_SECTION_KEYS.map((section) => [section, 'unconfigured']))
}

function initializeDraft() {
  draft.value = props.transition ? createAdvancedConfigDraft(props.transition) : null
  activeSection.value = 'basic'
  errors.value = createErrors()
}

function open() {
  initializeDraft()
  drawerVisible.value = true
}

function hasPendingChanges() {
  return Boolean(draft.value && props.transition && isAdvancedConfigDirty(props.transition, draft.value))
}

async function confirmDiscardPendingChanges() {
  if (!hasPendingChanges()) return true
  try {
    await ElMessageBox.confirm('放弃未应用的修改？', '关闭高级配置', { type: 'warning' })
    return true
  } catch {
    return false
  }
}

async function requestClose(done) {
  if (await confirmDiscardPendingChanges()) done()
}

async function cancel() {
  if (await confirmDiscardPendingChanges()) drawerVisible.value = false
}

function clearActiveSection() {
  if (!draft.value) return
  draft.value = clearAdvancedSection(draft.value, activeSection.value)
  errors.value[activeSection.value] = []
}

function applyPendingChanges() {
  if (!draft.value || !props.transition) return true
  const result = validateAdvancedConfig(draft.value, props.states)
  errors.value = result.errors
  if (!result.valid) {
    activeSection.value = result.firstSection
    return false
  }
  if (!hasPendingChanges()) return true
  emit('apply', createAdvancedConfigDraft(draft.value))
  initializeDraft()
  return true
}

function apply() {
  applyPendingChanges()
}

async function requestBack() {
  if (await confirmDiscardPendingChanges()) emit('back')
}

async function resetDiagramRoute() {
  try {
    await ElMessageBox.confirm('恢复自动布线后将清除当前手工路径，确认继续？', '恢复自动布线', { type: 'warning' })
    emit('reset-diagram-route')
  } catch {
    // Keep the current manual path when the user cancels.
  }
}

function errorFor(field) {
  const section = activeSection.value
  return errors.value[section]?.find((error) => error.field === field)?.message || ''
}

function addRoute() {
  draft.value.condition_routes.push({ value: '', state_id: null })
}

function stateName(stateId) {
  return props.states.find((state) => state.id === stateId)?.status_name || '-'
}

function transitionIdentity(item) {
  return item?.id ?? item?._client_id
}

function startTransitionDrag(item) {
  draggedTransitionIdentity.value = transitionIdentity(item)
}

function dropTransition(targetGroup, targetIndex) {
  if (draggedTransitionIdentity.value === null) return
  emit('move-transition', {
    transitionIdentity: draggedTransitionIdentity.value,
    targetGroup,
    targetIndex
  })
  draggedTransitionIdentity.value = null
}

function removeRoute(index) {
  draft.value.condition_routes.splice(index, 1)
}

function formPresetKey(fields) {
  if (!fields.length) return 'none'
  if (fields.length === 1 && fields[0].field === 'reason') return fields[0].required ? 'required_reason' : 'optional_reason'
  if (fields.length === 1 && fields[0].field === 'bug_type') return 'bug_type'
  if (fields.length === 2 && fields[0].field === 'bug_type' && fields[1].field === 'reason') return 'bug_reclassify'
  if (fields.length === 1 && fields[0].field === 'content') return 'information'
  if (fields.length === 1 && fields[0].field === 'effective_time' && fields[0].label === '实际开始日期') return 'actual_start_date'
  if (fields.length === 1 && fields[0].field === 'effective_time' && fields[0].label === '实际完成日期') return 'actual_end_date'
  return 'none'
}

function fixedFormConfig(key) {
  const presets = {
    none: [],
    required_reason: [{ field: 'reason', label: '原因', type: 'textarea', required: true }],
    optional_reason: [{ field: 'reason', label: '原因', type: 'textarea', required: false }],
    bug_type: [{ field: 'bug_type', label: 'Bug 类型', type: 'select', dictionary: 'bug_type', required: true }],
    bug_reclassify: [
      { field: 'bug_type', label: 'Bug 类型', type: 'select', dictionary: 'bug_type', required: true },
      { field: 'reason', label: '重分类原因', type: 'textarea', required: true }
    ],
    information: [{ field: 'content', label: '补充内容', type: 'textarea', required: true }],
    actual_start_date: [{ field: 'effective_time', label: '实际开始日期', type: 'date', required: true }],
    actual_end_date: [{ field: 'effective_time', label: '实际完成日期', type: 'date', required: true }]
  }
  return { fields: structuredClone(presets[key] || []) }
}

function toggleNotification(key, enabled) {
  draft.value[key] = enabled
    ? { type: 'notification', receiver: key === 'trigger_config' ? 'actor' : 'next_handler', title: '' }
    : null
}

defineExpose({ open, hasPendingChanges, applyPendingChanges, confirmDiscardPendingChanges })
</script>

<style scoped>
.workflow-advanced-drawer :deep(.el-drawer__header) {
  flex: 0 0 auto;
  margin: 0;
  padding: 16px 20px 14px;
  border-bottom: 1px solid #dfe5ec;
}

.workflow-advanced-drawer :deep(.el-drawer__body) {
  min-height: 0;
  padding: 0;
  overflow: hidden;
}

.drawer-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-right: 28px;
}

.drawer-header h2,
.section-heading h3,
.subsection-heading h4,
.notification-heading h4 {
  margin: 0;
  color: #172033;
  font-weight: 650;
}

.drawer-header h2 { font-size: 17px; }
.drawer-header p,
.section-heading p {
  margin: 5px 0 0;
  color: #667085;
  font-size: 12px;
}

.draft-status {
  flex: 0 0 auto;
  padding: 3px 7px;
  border: 1px solid #f1bf6a;
  border-radius: 4px;
  color: #9a5b00;
  background: #fff8e8;
  font-size: 12px;
}

.drawer-shell {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.state-action-shell {
  height: 100%;
  overflow-y: auto;
  padding: 18px 20px 24px;
  background: #f7f9fc;
}

.state-settings,
.action-group {
  padding: 16px;
  border: 1px solid #dfe5ec;
  border-radius: 6px;
  background: #fff;
}

.action-group { margin-top: 14px; }
.action-group-header,
.action-group-header > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.action-group-header h3 { margin: 0; color: #172033; font-size: 15px; }
.action-group-header span { color: #7a8595; font-size: 12px; }
.action-drop-zone { min-height: 72px; padding-top: 8px; }
.transition-card {
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 54px;
  margin-top: 8px;
  padding: 9px 12px;
  border: 1px solid #dfe5ec;
  border-radius: 6px;
  color: #344054;
  background: #fff;
  cursor: pointer;
  text-align: left;
}
.transition-card:hover { border-color: #84b3e8; background: #f4f8fe; }
.drag-handle { flex: 0 0 auto; margin-right: 10px; color: #7a8595; cursor: grab; }
.transition-card-copy { display: grid; min-width: 0; gap: 3px; }
.transition-card-copy strong { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.transition-card-copy small { color: #7a8595; }

.drawer-layout {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  flex: 1 1 auto;
  min-height: 0;
}

.section-nav {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 12px 8px;
  border-right: 1px solid #dfe5ec;
  background: #f7f9fc;
}

.section-nav-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 0 8px;
  border: 0;
  border-radius: 4px;
  color: #475467;
  background: transparent;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  text-align: left;
}

.section-nav-item:hover { background: #edf3fb; }
.section-nav-item.active { color: #1558b0; background: #e8f1ff; font-weight: 600; }

.section-indicator {
  width: 7px;
  height: 7px;
  flex: 0 0 7px;
  border-radius: 50%;
  background: #b8c1ce;
}

.section-indicator.configured { background: #2277d6; }
.section-indicator.invalid { background: #d92d20; }

.section-content {
  min-width: 0;
  overflow-y: auto;
  padding: 20px;
}

.editor-section { max-width: 720px; }
.section-heading { margin-bottom: 18px; }
.section-heading h3 { font-size: 16px; }

.form-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 4px 14px;
}

.form-grid :deep(.el-form-item) {
  display: block;
  min-width: 0;
  margin-bottom: 14px;
}

.form-grid :deep(.el-form-item__label) {
  display: flex;
  width: 100%;
  height: auto;
  padding: 0 0 6px;
  line-height: 20px;
}

.form-grid :deep(.el-form-item__content) {
  width: 100%;
  min-width: 0;
  margin-left: 0 !important;
}

.form-grid :deep(.el-select), .form-grid :deep(.el-input) { width: 100%; }
.full-width { grid-column: 1 / -1; }

.subsection-heading,
.field-editor-heading,
.notification-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.subsection-heading { margin: 10px 0 8px; }
.subsection-heading h4, .notification-heading h4 { font-size: 14px; }
.empty-hint { padding: 14px 0; color: #7a8595; font-size: 13px; }
.fixed-form-preview {
  display: grid;
  gap: 8px;
  margin-top: 12px;
  padding: 12px;
  border: 1px solid #dfe5ec;
  border-radius: 6px;
  background: #f7f9fc;
}
.fixed-form-preview > div { display: flex; justify-content: space-between; gap: 12px; }
.fixed-form-preview span { color: #7a8595; font-size: 12px; }

.route-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto;
  align-items: end;
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid #e8edf3;
}

.route-row :deep(.el-form-item) { margin-bottom: 0; }
.route-row :deep(.el-select), .route-row :deep(.el-input) { width: 100%; }
.row-remove { align-self: center; margin-top: 20px; }

.field-editor,
.notification-block {
  margin-top: 10px;
  padding: 14px;
  border: 1px solid #dfe5ec;
  border-radius: 6px;
  background: #fff;
}

.field-editor-heading { margin-bottom: 12px; color: #344054; font-size: 13px; }
.field-editor-actions { display: flex; align-items: center; gap: 2px; }
.field-editor-actions :deep(.el-button + .el-button) { margin-left: 0; }
.notification-block + .notification-block { margin-top: 12px; }
.notification-heading { margin-bottom: 12px; }

.diagram-routing-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
  padding: 10px 0;
  border-top: 1px solid #e8edf3;
  border-bottom: 1px solid #e8edf3;
}

.diagram-routing-row > div { display: grid; gap: 2px; }
.diagram-routing-row span { color: #7a8595; font-size: 12px; }
.diagram-routing-row strong { color: #344054; font-size: 13px; }

.drawer-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex: 0 0 auto;
  min-height: 64px;
  padding: 12px 20px;
  border-top: 1px solid #dfe5ec;
  background: #fff;
}

.footer-actions { display: flex; gap: 8px; }
</style>
