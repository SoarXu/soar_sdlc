<template>
  <div class="workflow-designer">
    <header class="workflow-designer-toolbar">
      <div>
        <h3>可视化工作流</h3>
        <p>拖拽状态节点，按住空白画布移动视角，点击节点或连线进行配置。</p>
      </div>
      <div class="workflow-designer-actions">
        <el-select
          :model-value="activeObjectType"
          size="small"
          class="workflow-object-select"
          @update:model-value="changeObjectType"
        >
          <el-option v-for="item in objectTypes" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-select v-model="initialStateId" size="small" class="workflow-initial-state-select" clearable placeholder="选择初始状态">
          <el-option
            v-for="state in enabledStates"
            :key="state.id"
            :label="`初始：${state.status_name}`"
            :value="state.id"
          />
        </el-select>
        <el-button size="small" @click="addState">新增状态</el-button>
        <el-button size="small" :loading="loading" @click="organizeLayout">整理布局</el-button>
        <el-button size="small" @click="fitToContent">适应视图</el-button>
        <el-button size="small" @click="resetViewport">回到原点</el-button>
        <el-button size="small" :loading="loading" @click="applyTemplate">套用模板</el-button>
        <el-button size="small" type="primary" :loading="saving" @click="saveGraph">保存流程图</el-button>
      </div>
    </header>

    <div class="workflow-designer-main">
      <div
        ref="workflowCanvasElement"
        class="workflow-canvas"
        :class="{ panning: viewportDrag.active }"
        :style="canvasGridStyle"
      >
        <svg
          ref="workflowSvgElement"
          class="workflow-svg"
          :viewBox="`0 0 ${viewportSize.width} ${viewportSize.height}`"
          @mousedown.self.prevent="startViewportDrag"
          @click.self="clearSelection"
        >
          <defs>
            <marker
              id="workflow-arrow"
              viewBox="0 0 10 10"
              refX="9"
              refY="5"
              markerWidth="7"
              markerHeight="7"
              orient="auto-start-reverse"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
            </marker>
          </defs>
          <g :transform="`translate(${viewportOffset.x}, ${viewportOffset.y})`">
            <g
              v-for="edge in transitionViews"
              :key="edge.key"
              class="workflow-edge"
              :class="{ selected: isSelectedTransition(edge.transition), disabled: !edge.transition.enabled }"
              @click.stop="selectTransition(edge.transition)"
            >
              <path class="workflow-edge-path" :d="edge.path" />
              <rect :x="edge.labelX - 40" :y="edge.labelY - 13" width="80" height="26" rx="5" />
              <text :x="edge.labelX" :y="edge.labelY + 4">{{ edge.transition.action_name }}</text>
              <template v-if="isSelectedTransition(edge.transition) && edge.transition.from_state_id !== edge.transition.to_state_id">
                <path
                  v-for="segment in editableSegments(edge)"
                  :key="`${edge.key}-segment-${segment.index}`"
                  class="workflow-edge-segment-hit"
                  :class="segment.orientation"
                  :d="segment.path"
                  @mousedown.stop.prevent="startSegmentDrag(edge, segment.index, $event)"
                />
                <circle
                  class="workflow-edge-endpoint"
                  :cx="edge.start.x"
                  :cy="edge.start.y"
                  r="4"
                  @mousedown.stop.prevent="startEndpointDrag(edge, 'source', $event)"
                />
                <circle
                  class="workflow-edge-endpoint"
                  :cx="edge.end.x"
                  :cy="edge.end.y"
                  r="4"
                  @mousedown.stop.prevent="startEndpointDrag(edge, 'target', $event)"
                />
              </template>
            </g>
            <g
              v-for="state in renderedStates"
              :key="state.id"
              class="workflow-node"
              :class="{
                selected: isSelectedState(state),
                terminal: state.category === 'terminal',
                inactive: state.enabled === false
              }"
              :transform="`translate(${state.x}, ${state.y})`"
              @mousedown.stop.prevent="startDrag(state, $event)"
              @click.stop="handleStateClick(state)"
            >
              <rect :fill="state.enabled === false ? '#ffffff' : (state.color || '#2563eb')" width="118" height="42" rx="6" />
              <text x="59" :y="state.enabled === false ? 19 : 26">{{ state.status_name }}</text>
              <text v-if="state.enabled === false" class="workflow-node-status" x="59" y="34">已停用</text>
              <g
                v-if="nodeActionForState(state)"
                class="workflow-node-action-badge"
                :class="{ selected: activeNodeActionStateId === state.id }"
                transform="translate(106, 7)"
                role="button"
                tabindex="0"
                :aria-label="nodeActionAriaLabel(state)"
                @mousedown.stop
                @click.stop="toggleNodeActionMenu(nodeActionForState(state), $event)"
                @keydown.enter.prevent="toggleNodeActionMenu(nodeActionForState(state), $event)"
                @keydown.space.prevent="toggleNodeActionMenu(nodeActionForState(state), $event)"
                @keydown.esc.stop.prevent="closeNodeActionMenu"
              >
                <title>{{ nodeActionAriaLabel(state) }}</title>
                <circle r="10" />
                <text y="4">{{ nodeActionForState(state).actions.length }}</text>
              </g>
            </g>
          </g>
        </svg>
        <div
          v-if="activeNodeActionMenu"
          class="workflow-node-action-menu"
          :style="nodeActionMenuStyle"
          role="menu"
          @click.stop
          @keydown.esc.stop.prevent="closeNodeActionMenu"
        >
          <button
            v-for="action in activeNodeActionMenu.actions"
            :key="transitionKey(action)"
            type="button"
            class="workflow-node-action-menu-item"
            :class="{ inactive: action.enabled === false }"
            role="menuitem"
            @click="selectNodeAction(action)"
          >
            <span>{{ action.action_name }}</span>
            <small v-if="action.enabled === false">已停用</small>
          </button>
        </div>
      </div>

    </div>
    <WorkflowAdvancedConfigDrawer
      ref="advancedDrawer"
      v-model="advancedDrawerVisible"
      :state="drawerState"
      :transition="selectedTransition"
      :transitions="transitions"
      :states="states"
      :role-options="roleOptions"
      :target-types="targetTypes"
      @apply="applyAdvancedDraft"
      @select-transition="selectTransition"
      @move-transition="moveTransition"
      @add-transition="addTransition"
      @remove-transition="removeSelectedTransition"
      @reset-diagram-route="resetSelectedDiagramRoute"
      @back="returnToStateActions"
    />
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import WorkflowAdvancedConfigDrawer from './WorkflowAdvancedConfigDrawer.vue'
import {
  createWorkflowDefinition,
  fetchWorkflowDefinitionGraph,
  fetchWorkflowDefinitionTemplatePreview,
  fetchWorkflowDefinitions,
  saveWorkflowDefinitionGraph
} from '../api/workflowDefinitions'
import { projectWorkflowCanvas } from '../utils/workflowCanvasProjection'
import {
  applyGeneratedRoutesFromViews,
  createWorkflowDragFrame
} from '../utils/workflowDragFrame'
import { buildWorkflowEdgeViews } from '../utils/workflowEdgePath'
import { layoutWorkflowWithElk } from '../utils/workflowElkLayout'
import { workflowGraphSnapshot } from '../utils/workflowGraphSnapshot'
import {
  createManualDiagramConfig,
  isManualDiagramRoute,
  moveManualAnchor,
  moveManualSegment
} from '../utils/workflowManualRoute'
import { requestWorkflowOrganization } from '../utils/workflowLayoutInteraction'
import {
  normalizeWorkflowTransition as normalizeTransition,
  serializeWorkflowTransition as serializeTransition,
  unsupportedWorkflowConfigSections
} from '../utils/workflowTransitionConfig'
import { applyAdvancedConfigDraft } from '../utils/workflowAdvancedConfig'
import { moveStateTransition, nextGroupSortOrder } from '../utils/workflowTransitionOrdering'
import {
  applyPanDelta,
  clampViewport,
  fitViewportToNodes,
  workflowCanvasSize
} from '../utils/workflowViewport'

const props = defineProps({
  configId: { type: Number, required: true },
  configName: { type: String, default: '' },
  roleOptions: { type: Array, default: () => [] }
})

const objectTypes = [
  { label: '需求', value: 'requirement' },
  { label: '任务', value: 'task' },
  { label: '缺陷', value: 'bug' }
]
const targetTypes = [
  { label: '当前操作人', value: 'actor' },
  { label: '手动指定', value: 'explicit_owner' },
  { label: '创建人', value: 'creator' },
  { label: '上一处理人', value: 'previous_handler' },
  { label: '项目负责人', value: 'project_owner' },
  { label: '需求负责人', value: 'requirement_owner' },
  { label: '来源负责人', value: 'source_owner' },
  { label: '任务确认人', value: 'task_confirmation' },
  { label: 'Bug 验证人', value: 'bug_verifier' },
  { label: '待验证时的 Bug 验证人', value: 'bug_verifier_if_pending_verification' },
  { label: '测试执行人', value: 'test_executor' },
  { label: '测试用例默认测试人', value: 'test_case_default_tester' },
  { label: '项目角色', value: 'project_role' },
  { label: '保持当前处理人', value: 'keep_current' },
  { label: '需求提出人', value: 'proposer' },
  { label: '缺陷报告人', value: 'reporter' },
  { label: '上次修复人', value: 'last_resolver' },
  { label: '无处理人', value: 'none' }
]
const minimumCanvas = { width: 2400, height: 1400 }
const viewportSize = { width: 980, height: 540 }
const NODE_DRAG_THRESHOLD = 4
const activeObjectType = ref('requirement')
const definition = ref(null)
const replaceExistingTransitionsOnSave = ref(false)
const states = ref([])
const transitions = ref([])
const initialStateId = ref(null)
const selectedKind = ref('')
const selectedKey = ref('')
const loading = ref(false)
const saving = ref(false)
const savedGraphSnapshot = ref('')
const advancedDrawer = ref(null)
const advancedDrawerVisible = ref(false)
const suppressCanvasClamp = ref(false)
const suppressedStateClickId = ref(null)
const dragFrame = ref(null)
const workflowCanvasElement = ref(null)
const workflowSvgElement = ref(null)
const canvasRenderedSize = reactive({ ...viewportSize })
const activeNodeActionStateId = ref(null)
const activeNodeActionAnchor = reactive({ left: 0, top: 0, bottom: 0 })
const viewportOffset = reactive({ x: 0, y: 0 })
const dragging = reactive({
  state: null,
  startX: 0,
  startY: 0,
  originX: 0,
  originY: 0,
  pendingX: 0,
  pendingY: 0,
  moved: false,
  frame: 0
})
const viewportDrag = reactive({ active: false, startX: 0, startY: 0, originX: 0, originY: 0 })
const routeDrag = reactive({
  kind: '',
  transition: null,
  endpoint: '',
  segmentIndex: -1,
  originalConfig: null
})
const enabledStates = computed(() => states.value.filter((state) => state.enabled))
const canvasProjection = computed(() => projectWorkflowCanvas(states.value, transitions.value))
const fullTransitionViews = computed(() => (
  buildWorkflowEdgeViews(states.value, canvasProjection.value.routedTransitions, transitionKey)
))
const renderedStates = computed(() => dragFrame.value?.states || states.value)
const transitionViews = computed(() => dragFrame.value?.transitionViews || fullTransitionViews.value)
const canvasEdgeViews = computed(() => transitionViews.value)
const nodeActionsByStateId = computed(() => new Map(states.value.flatMap((state) => {
  const actions = canvasProjection.value.stateActionsByStateId.get(state.id) || []
  return actions.length ? [[state.id, { stateId: state.id, actions }]] : []
})))
const canvasSize = computed(() => (
  workflowCanvasSize(renderedStates.value, minimumCanvas, undefined, canvasEdgeViews.value)
))
const activeNodeActionMenu = computed(() => (
  nodeActionsByStateId.value.get(activeNodeActionStateId.value) || null
))
const nodeActionMenuStyle = computed(() => {
  const menu = activeNodeActionMenu.value
  if (!menu) return {}
  const renderedWidth = Math.max(240, canvasRenderedSize.width)
  const renderedHeight = Math.max(240, canvasRenderedSize.height)
  const width = Math.min(200, renderedWidth - 16)
  const height = Math.min(12 + menu.actions.length * 36, renderedHeight - 16)
  const belowTop = activeNodeActionAnchor.bottom + 6
  const top = belowTop + height <= renderedHeight - 8
    ? belowTop
    : Math.max(8, activeNodeActionAnchor.top - height - 6)
  const left = Math.max(8, Math.min(renderedWidth - width - 8, activeNodeActionAnchor.left))
  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    maxHeight: `${height}px`
  }
})

const selectedState = computed(() => (
  selectedKind.value === 'state'
    ? states.value.find((item) => item.id === selectedKey.value)
    : null
))
const selectedTransition = computed(() => (
  selectedKind.value === 'transition'
    ? transitions.value.find((item) => transitionKey(item) === selectedKey.value)
    : null
))
const drawerState = computed(() => {
  if (selectedState.value) return selectedState.value
  if (!selectedTransition.value) return null
  return states.value.find((item) => item.id === selectedTransition.value.from_state_id) || null
})
const selectedUnsupportedSections = computed(() => (
  selectedTransition.value ? unsupportedWorkflowConfigSections(selectedTransition.value) : []
))
const canvasGridStyle = computed(() => ({
  backgroundPosition: `${viewportOffset.x}px ${viewportOffset.y}px`
}))
const currentGraphSnapshot = computed(() => workflowGraphSnapshot({
  definitionId: definition.value?.id,
  objectType: activeObjectType.value,
  initialStateId: initialStateId.value,
  states: states.value,
  transitions: transitions.value
}))
const hasUnsavedGraphChanges = computed(() => (
  replaceExistingTransitionsOnSave.value || (
    savedGraphSnapshot.value !== '' && savedGraphSnapshot.value !== currentGraphSnapshot.value
  )
))

watch(canvasSize, (nextCanvas) => {
  if (dragging.state || suppressCanvasClamp.value) return
  clampCurrentViewport(nextCanvas)
}, { flush: 'sync' })

watch(() => props.configId, () => loadDefinition())

onBeforeRouteLeave(async () => confirmDiscardWorkflowChanges())

let workflowCanvasResizeObserver = null
let suppressedStateClickTimer = null

onMounted(() => {
  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
  window.addEventListener('mousemove', onRouteDrag)
  window.addEventListener('mouseup', stopRouteDrag)
  window.addEventListener('mousemove', onViewportDrag)
  window.addEventListener('mouseup', stopViewportDrag)
  window.addEventListener('keydown', onDesignerKeydown)
  window.addEventListener('beforeunload', onBeforeUnload)
  nextTick(() => {
    syncCanvasRenderedSize()
    if (typeof ResizeObserver !== 'undefined' && workflowCanvasElement.value) {
      workflowCanvasResizeObserver = new ResizeObserver(syncCanvasRenderedSize)
      workflowCanvasResizeObserver.observe(workflowCanvasElement.value)
    }
  })
  loadDefinition()
})

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
  window.removeEventListener('mousemove', onRouteDrag)
  window.removeEventListener('mouseup', stopRouteDrag)
  window.removeEventListener('mousemove', onViewportDrag)
  window.removeEventListener('mouseup', stopViewportDrag)
  window.removeEventListener('keydown', onDesignerKeydown)
  window.removeEventListener('beforeunload', onBeforeUnload)
  if (dragging.frame) cancelAnimationFrame(dragging.frame)
  if (suppressedStateClickTimer) clearTimeout(suppressedStateClickTimer)
  workflowCanvasResizeObserver?.disconnect()
})

function syncCanvasRenderedSize() {
  if (!workflowCanvasElement.value) return
  const bounds = workflowCanvasElement.value.getBoundingClientRect()
  canvasRenderedSize.width = bounds.width || viewportSize.width
  canvasRenderedSize.height = bounds.height || viewportSize.height
}

async function loadDefinition({ discardPendingChanges = true } = {}) {
  if (!props.configId) return
  if (discardPendingChanges && !await confirmDiscardWorkflowChanges()) return
  loading.value = true
  try {
    const list = await fetchWorkflowDefinitions({
      object_type: activeObjectType.value,
      scope_type: 'assignee_rule_config',
      scope_id: props.configId
    })
    let current = list.data[0]
    if (!current) {
      const created = await createWorkflowDefinition({
        name: `${props.configName || '工作流'}-${objectTypes.find((item) => item.value === activeObjectType.value)?.label}`,
        object_type: activeObjectType.value,
        scope_type: 'assignee_rule_config',
        scope_id: props.configId,
        enabled: true
      })
      current = created.data
    }
    definition.value = current
    const graph = await fetchWorkflowDefinitionGraph(current.id)
    applyGraph(graph.data)
    replaceExistingTransitionsOnSave.value = false
    captureSavedGraphSnapshot()
  } finally {
    loading.value = false
  }
}

async function organizeLayout() {
  loading.value = true
  try {
    const result = await requestWorkflowOrganization({
      states: states.value,
      transitions: transitions.value,
      initialStateId: initialStateId.value,
      confirm: () => ElMessageBox.confirm('整理布局将重新排列全部节点并清除手工布线，确认继续？', '整理布局', { type: 'warning' }),
      notifyEmpty: () => ElMessage.info('当前没有可整理的状态节点')
    })
    if (!result.organized) return
    closeNodeActionMenu()
    states.value = result.states
    transitions.value = result.transitions
    fitToContent()
  } catch {
    ElMessage.error('整理布局失败，当前流程图未更改')
  } finally {
    loading.value = false
  }
}

function applyGraph(graph) {
  stopRouteDrag()
  closeNodeActionMenu()
  definition.value = graph.definition || definition.value
  states.value = (graph.states || []).map((item) => ({ ...item }))
  transitions.value = (graph.transitions || []).map((item) => normalizeTransition({
    ...item,
    _client_id: `transition-${item.id}`
  }))
  initialStateId.value = graph.definition?.initial_state_id ?? null
  if (!states.value.length) {
    selectedKind.value = ''
    selectedKey.value = ''
  }
  fitToContent()
}

async function applyTemplate() {
  if (!definition.value?.id) return
  if (!await confirmDiscardWorkflowChanges({
    force: true,
    title: '套用模板',
    message: '套用模板会覆盖当前流程图，未保存修改将被放弃，确认继续？'
  })) return
  loading.value = true
  try {
    const graph = await fetchWorkflowDefinitionTemplatePreview(definition.value.id)
    let organized
    try {
      organized = await layoutWorkflowWithElk(
        graph.data.states || [],
        graph.data.transitions || [],
        graph.data.definition?.initial_state_id ?? null
      )
    } catch {
      ElMessage.error('模板布局失败，当前流程图未更改')
      return
    }
    applyGraph({
      ...graph.data,
      states: organized.states,
      transitions: organized.transitions
    })
    replaceExistingTransitionsOnSave.value = true
    ElMessage.success('模板已套用')
  } finally {
    loading.value = false
  }
}

async function changeObjectType(nextObjectType) {
  if (nextObjectType === activeObjectType.value) return
  if (!await confirmDiscardWorkflowChanges()) return
  activeObjectType.value = nextObjectType
  await loadDefinition({ discardPendingChanges: false })
}

async function saveGraph() {
  if (!definition.value?.id) return
  if (transitions.value.some((item) => unsupportedWorkflowConfigSections(item).length)) {
    ElMessage.error('存在未支持的历史配置，请先完成迁移后再保存。')
    return
  }
  if (advancedDrawer.value?.applyPendingChanges?.() === false) {
    ElMessage.warning('请先修正高级配置中的校验错误')
    return
  }
  saving.value = true
  try {
    const payload = {
      initial_state_id: initialStateId.value,
      replace_existing_transitions: replaceExistingTransitionsOnSave.value,
      states: states.value.map(({ definition_id, ...item }) => item),
      transitions: transitions.value.map((item) => serializeTransition(item))
    }
    const graph = await saveWorkflowDefinitionGraph(definition.value.id, payload)
    applyGraph(graph.data)
    replaceExistingTransitionsOnSave.value = false
    captureSavedGraphSnapshot()
    ElMessage.success('流程图已保存')
  } finally {
    saving.value = false
  }
}

function addState() {
  const index = states.value.length + 1
  const temporaryId = nextTemporaryStateId()
  states.value.push({
    id: temporaryId,
    status_name: `状态${index}`,
    category: 'normal',
    color: '#2563eb',
    x: 120 + (index % 4) * 180,
    y: 90 + Math.floor(index / 4) * 120,
    sort_order: index * 10,
    enabled: true
  })
  selectState(states.value[states.value.length - 1])
}

function nextTemporaryStateId() {
  return Math.min(-1, ...states.value.map((state) => state.id - 1))
}

function addTransition(group = 'more') {
  const from = drawerState.value
  if (!from) return
  if (states.value.length < 2) {
    ElMessage.warning('至少需要两个状态')
    return
  }
  const to = states.value.find((state) => state.id !== from.id)
  const transition = normalizeTransition({
    action_name: `流转${transitions.value.length + 1}`,
    from_state_id: from.id,
    to_state_id: to.id,
    _client_id: `new-transition-${Date.now()}-${transitions.value.length + 1}`,
    allowed_roles: '',
    handler_rule: {
      target_type: 'keep_current',
      target_roles: '',
      fallback_type: 'keep_current',
      fallback_roles: ''
    },
    enabled: true,
    sort_order: nextGroupSortOrder(transitions.value, from.id, group),
    ui_config: { list_display: group }
  })
  transitions.value.push(transition)
  selectTransition(transition)
}

function handleStateClick(state) {
  if (suppressedStateClickId.value === state.id) {
    suppressedStateClickId.value = null
    if (suppressedStateClickTimer) clearTimeout(suppressedStateClickTimer)
    suppressedStateClickTimer = null
    return
  }
  selectState(state)
}

function selectState(state) {
  stopRouteDrag()
  closeNodeActionMenu()
  selectedKind.value = 'state'
  selectedKey.value = state.id
  advancedDrawerVisible.value = true
  advancedDrawer.value?.open?.()
}

function selectTransition(transition) {
  stopRouteDrag()
  closeNodeActionMenu()
  selectedKind.value = 'transition'
  selectedKey.value = transitionKey(transition)
  advancedDrawerVisible.value = true
  advancedDrawer.value?.open?.()
}

function moveTransition({ transitionIdentity, targetGroup, targetIndex }) {
  transitions.value = moveStateTransition(transitions.value, transitionIdentity, targetGroup, targetIndex)
}

function returnToStateActions() {
  if (!drawerState.value) return
  selectedKind.value = 'state'
  selectedKey.value = drawerState.value.id
}

function clearSelection() {
  stopRouteDrag()
  closeNodeActionMenu()
  selectedKind.value = ''
  selectedKey.value = ''
  advancedDrawerVisible.value = false
}

function removeSelectedState() {
  if (!selectedState.value) return
  const stateId = selectedState.value.id
  transitions.value = transitions.value.filter((item) => (
    item.from_state_id !== stateId && item.to_state_id !== stateId
  ))
  states.value = states.value.filter((item) => item.id !== stateId)
  if (initialStateId.value === stateId) initialStateId.value = null
  clearSelection()
}

function removeSelectedTransition() {
  if (!selectedTransition.value) return
  if (selectedTransition.value.id) {
    selectedTransition.value.enabled = false
    returnToStateActions()
    return
  }
  const key = transitionKey(selectedTransition.value)
  transitions.value = transitions.value.filter((item) => transitionKey(item) !== key)
  clearSelection()
}

function applyAdvancedDraft(draft) {
  if (!selectedTransition.value || selectedUnsupportedSections.value.length) return
  applyAdvancedConfigDraft(selectedTransition.value, draft)
}

function resetSelectedDiagramRoute() {
  if (!selectedTransition.value) return
  selectedTransition.value.diagram_config = null
}

function captureSavedGraphSnapshot() {
  savedGraphSnapshot.value = currentGraphSnapshot.value
}

function hasPendingWorkflowChanges() {
  return hasUnsavedGraphChanges.value || Boolean(advancedDrawer.value?.hasPendingChanges?.())
}

async function confirmDiscardWorkflowChanges({
  force = false,
  title = '放弃未保存修改',
  message = '当前流程图或高级配置有未保存修改，确认放弃？'
} = {}) {
  if (!force && !hasPendingWorkflowChanges()) return true
  try {
    await ElMessageBox.confirm(message, title, { type: 'warning' })
    return true
  } catch {
    return false
  }
}

defineExpose({ confirmDiscardWorkflowChanges })

function onBeforeUnload(event) {
  if (!hasPendingWorkflowChanges()) return
  event.preventDefault()
  event.returnValue = ''
}

function roleSummary(roles) {
  if (!Array.isArray(roles) || !roles.length) return '未限制'
  return roles
    .map((value) => props.roleOptions.find((role) => role.value === value)?.label || value)
    .join('、')
}

function handlerSummary(transition) {
  const rule = transition.handler_rule || {}
  const target = handlerTypeSummary(rule.target_type, transition.handler_target_roles)
  const fallback = handlerTypeSummary(rule.fallback_type, transition.handler_fallback_roles)
  return `${target}；兜底 ${fallback}`
}

function handlerTypeSummary(type, roles) {
  const label = targetTypes.find((item) => item.value === type)?.label || '未设置'
  return type === 'project_role' ? `${label}（${roleSummary(roles)}）` : label
}

function toggleNodeActionMenu(trigger, event) {
  if (activeNodeActionStateId.value === trigger.stateId) {
    closeNodeActionMenu()
    return
  }
  syncCanvasRenderedSize()
  const triggerBounds = event.currentTarget.getBoundingClientRect()
  const canvasBounds = workflowCanvasElement.value.getBoundingClientRect()
  activeNodeActionAnchor.left = triggerBounds.left - canvasBounds.left
  activeNodeActionAnchor.top = triggerBounds.top - canvasBounds.top
  activeNodeActionAnchor.bottom = triggerBounds.bottom - canvasBounds.top
  activeNodeActionStateId.value = trigger.stateId
}

function closeNodeActionMenu() {
  activeNodeActionStateId.value = null
}

function nodeActionForState(state) {
  return nodeActionsByStateId.value.get(state.id) || null
}

function nodeActionAriaLabel(state) {
  const count = nodeActionForState(state)?.actions.length || 0
  return `${state.status_name}：${count} 个同状态操作`
}

function selectNodeAction(transition) {
  closeNodeActionMenu()
  selectTransition(transition)
}

function editableSegments(edge) {
  const points = edge.points || []
  const segments = []
  for (let index = 1; index < points.length - 2; index += 1) {
    const from = points[index]
    const to = points[index + 1]
    const orientation = from.y === to.y ? 'horizontal' : (from.x === to.x ? 'vertical' : '')
    if (!orientation) continue
    segments.push({
      index,
      orientation,
      path: `M ${from.x} ${from.y} L ${to.x} ${to.y}`
    })
  }
  return segments
}

function startEndpointDrag(edge, endpoint, event) {
  if (!beginRouteDrag(edge)) return
  routeDrag.kind = 'endpoint'
  routeDrag.endpoint = endpoint
}

function startSegmentDrag(edge, segmentIndex, event) {
  if (!beginRouteDrag(edge)) return
  routeDrag.kind = 'segment'
  routeDrag.segmentIndex = segmentIndex
}

function beginRouteDrag(edge) {
  if (dragging.state || viewportDrag.active || routeDrag.kind) return false
  const transition = edge.transition
  const from = stateById(transition.from_state_id)
  const to = stateById(transition.to_state_id)
  if (!from || !to || from.id === to.id) return false
  closeNodeActionMenu()
  routeDrag.transition = transition
  routeDrag.originalConfig = transition.diagram_config
    ? structuredClone(transition.diagram_config)
    : null
  if (!isManualDiagramRoute(transition.diagram_config)) {
    transition.diagram_config = createManualDiagramConfig(edge, from, to)
  }
  return Boolean(transition.diagram_config)
}

function onRouteDrag(event) {
  if (!routeDrag.kind || !routeDrag.transition) return
  const from = stateById(routeDrag.transition.from_state_id)
  const to = stateById(routeDrag.transition.to_state_id)
  const point = eventToCanvasPoint(event)
  const next = routeDrag.kind === 'endpoint'
    ? moveManualAnchor(routeDrag.transition.diagram_config, routeDrag.endpoint, point, from, to)
    : moveManualSegment(routeDrag.transition.diagram_config, routeDrag.segmentIndex, point, from, to)
  if (next) routeDrag.transition.diagram_config = next
}

function stopRouteDrag() {
  routeDrag.kind = ''
  routeDrag.transition = null
  routeDrag.endpoint = ''
  routeDrag.segmentIndex = -1
  routeDrag.originalConfig = null
}

function cancelRouteDrag() {
  if (!routeDrag.kind || !routeDrag.transition) return
  routeDrag.transition.diagram_config = routeDrag.originalConfig
    ? structuredClone(routeDrag.originalConfig)
    : null
  stopRouteDrag()
}

function onDesignerKeydown(event) {
  if (event.key !== 'Escape' || !routeDrag.kind) return
  event.preventDefault()
  cancelRouteDrag()
}

function eventToCanvasPoint(event) {
  const bounds = workflowSvgElement.value.getBoundingClientRect()
  const scale = Math.min(bounds.width / viewportSize.width, bounds.height / viewportSize.height) || 1
  const offsetX = (bounds.width - viewportSize.width * scale) / 2
  const offsetY = (bounds.height - viewportSize.height * scale) / 2
  return {
    x: (event.clientX - bounds.left - offsetX) / scale - viewportOffset.x,
    y: (event.clientY - bounds.top - offsetY) / scale - viewportOffset.y
  }
}

function stateById(stateId) {
  return states.value.find((state) => state.id === stateId) || null
}

function startDrag(state, event) {
  if (routeDrag.kind) return
  closeNodeActionMenu()
  dragging.state = stateById(state.id)
  if (!dragging.state) return
  dragFrame.value = null
  dragging.startX = event.clientX
  dragging.startY = event.clientY
  dragging.originX = state.x
  dragging.originY = state.y
  dragging.pendingX = event.clientX
  dragging.pendingY = event.clientY
  dragging.moved = false
}

function onDrag(event) {
  if (!dragging.state) return
  dragging.pendingX = event.clientX
  dragging.pendingY = event.clientY
  const deltaX = event.clientX - dragging.startX
  const deltaY = event.clientY - dragging.startY
  if (!dragging.moved) {
    dragging.moved = deltaX * deltaX + deltaY * deltaY > NODE_DRAG_THRESHOLD * NODE_DRAG_THRESHOLD
  }
  if (!dragging.moved) return
  if (!dragging.frame) dragging.frame = requestAnimationFrame(flushNodeDrag)
}

function flushNodeDrag() {
  dragging.frame = 0
  if (!dragging.state) return
  const x = Math.max(20, Math.min(canvasSize.value.right - 140, dragging.originX + dragging.pendingX - dragging.startX))
  const y = Math.max(20, Math.min(canvasSize.value.bottom - 70, dragging.originY + dragging.pendingY - dragging.startY))
  dragFrame.value = createWorkflowDragFrame(
    states.value,
    canvasProjection.value.routedTransitions,
    dragging.state.id,
    { x, y },
    transitionKey
  )
}

function clampCurrentViewport(nextCanvas = canvasSize.value) {
  const next = clampViewport({ x: viewportOffset.x, y: viewportOffset.y }, nextCanvas, viewportSize)
  viewportOffset.x = next.x
  viewportOffset.y = next.y
}

function stopDrag() {
  if (!dragging.state) return
  const draggedStateId = dragging.state.id
  if (dragging.frame) {
    cancelAnimationFrame(dragging.frame)
    dragging.frame = 0
    flushNodeDrag()
  }
  const finalState = dragFrame.value?.states.find((state) => state.id === draggedStateId)
  if (finalState) {
    dragging.state.x = finalState.x
    dragging.state.y = finalState.y
    transitions.value = applyGeneratedRoutesFromViews(
      dragFrame.value.states,
      transitions.value,
      dragFrame.value.transitionViews,
      transitionKey
    )
  }
  if (dragging.moved) {
    suppressedStateClickId.value = draggedStateId
    if (suppressedStateClickTimer) clearTimeout(suppressedStateClickTimer)
    suppressedStateClickTimer = setTimeout(() => {
      if (suppressedStateClickId.value === draggedStateId) suppressedStateClickId.value = null
      suppressedStateClickTimer = null
    }, 0)
  }
  suppressCanvasClamp.value = true
  dragging.state = null
  dragFrame.value = null
  nextTick(() => {
    suppressCanvasClamp.value = false
  })
}

function startViewportDrag(event) {
  if (routeDrag.kind) return
  closeNodeActionMenu()
  viewportDrag.active = true
  viewportDrag.startX = event.clientX
  viewportDrag.startY = event.clientY
  viewportDrag.originX = viewportOffset.x
  viewportDrag.originY = viewportOffset.y
}

function onViewportDrag(event) {
  if (!viewportDrag.active || dragging.state) return
  const next = applyPanDelta(
    { x: viewportDrag.originX, y: viewportDrag.originY },
    { dx: event.clientX - viewportDrag.startX, dy: event.clientY - viewportDrag.startY },
    canvasSize.value,
    viewportSize
  )
  viewportOffset.x = next.x
  viewportOffset.y = next.y
}

function stopViewportDrag() {
  viewportDrag.active = false
}

function fitToContent() {
  const next = fitViewportToNodes(states.value, canvasSize.value, viewportSize, fullTransitionViews.value)
  viewportOffset.x = next.x
  viewportOffset.y = next.y
}

function resetViewport() {
  const next = clampViewport({ x: 0, y: 0 }, canvasSize.value, viewportSize)
  viewportOffset.x = next.x
  viewportOffset.y = next.y
}

function isSelectedState(state) {
  return selectedKind.value === 'state' && selectedKey.value === state.id
}

function isSelectedTransition(transition) {
  return selectedKind.value === 'transition' && selectedKey.value === transitionKey(transition)
}

function transitionKey(transition) {
  return transition.id || transition._client_id
}

</script>

<style scoped>
.workflow-designer {
  position: relative;
  border: 1px solid #d8dee8;
  border-radius: 8px;
  overflow: hidden;
  background: #fff;
}

.workflow-designer-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  border-bottom: 1px solid #e5e7eb;
  background: #f8fafc;
}

.workflow-designer-toolbar h3 {
  margin: 0;
  font-size: 16px;
  color: #0f172a;
}

.workflow-designer-toolbar p {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 12px;
}

.workflow-designer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.workflow-object-select {
  width: 110px;
}

.workflow-initial-state-select {
  width: 180px;
}

.workflow-designer-main {
  display: block;
  min-height: 540px;
}

.workflow-canvas {
  position: relative;
  background:
    linear-gradient(#eef2f7 1px, transparent 1px),
    linear-gradient(90deg, #eef2f7 1px, transparent 1px);
  background-size: 24px 24px;
  cursor: grab;
  overflow: hidden;
  user-select: none;
}

.workflow-canvas.panning {
  cursor: grabbing;
}

.workflow-svg {
  width: 100%;
  height: 540px;
  display: block;
}

.workflow-edge {
  cursor: pointer;
}

.workflow-edge-path {
  fill: none;
  stroke: #94a3b8;
  stroke-width: 2;
  marker-end: url(#workflow-arrow);
}

.workflow-edge rect {
  fill: #fff;
  stroke: #d7dde7;
}

.workflow-edge text {
  text-anchor: middle;
  font-size: 12px;
  fill: #334155;
  user-select: none;
}

.workflow-edge.selected .workflow-edge-path {
  stroke: #1d4ed8;
  stroke-width: 3;
}

.workflow-edge.selected rect {
  stroke: #1d4ed8;
}

.workflow-edge.disabled .workflow-edge-path {
  stroke: #a8b0bc;
  stroke-dasharray: 7 5;
}

.workflow-edge.disabled rect {
  fill: #f4f6f8;
  stroke-dasharray: 4 3;
}

.workflow-edge.disabled text { fill: #7a8595; }

.workflow-edge-segment-hit {
  fill: none;
  stroke: transparent;
  stroke-width: 12;
  pointer-events: stroke;
  marker-end: none;
}

.workflow-edge-segment-hit.horizontal { cursor: row-resize; }
.workflow-edge-segment-hit.vertical { cursor: col-resize; }

.workflow-edge-endpoint {
  fill: #ffffff;
  stroke: #1d4ed8;
  stroke-width: 2;
  cursor: crosshair;
}

.workflow-node {
  cursor: move;
}

.workflow-node rect {
  stroke: rgba(15, 23, 42, 0.16);
  stroke-width: 1;
  filter: drop-shadow(0 5px 10px rgba(15, 23, 42, 0.14));
}

.workflow-node text {
  fill: #fff;
  font-size: 13px;
  font-weight: 600;
  text-anchor: middle;
  user-select: none;
}

.workflow-node.terminal rect {
  rx: 12;
}

.workflow-node.selected rect {
  stroke: #0f172a;
  stroke-width: 3;
}

.workflow-node.inactive rect {
  stroke: #94a3b8;
  stroke-width: 2;
  stroke-dasharray: 6 4;
  filter: none;
}

.workflow-node.inactive text {
  fill: #475569;
}

.workflow-node .workflow-node-status {
  fill: #94a3b8;
  font-size: 10px;
  font-weight: 500;
}

.workflow-node-action-badge {
  cursor: pointer;
  outline: none;
}

.workflow-node-action-badge circle {
  fill: #ffffff;
  stroke: #2563eb;
  stroke-width: 1.5;
  filter: none;
}

.workflow-node .workflow-node-action-badge text {
  fill: #1e40af;
  font-size: 10px;
  font-weight: 600;
  text-anchor: middle;
  user-select: none;
}

.workflow-node-action-badge:hover circle,
.workflow-node-action-badge:focus-visible circle,
.workflow-node-action-badge.selected circle {
  fill: #eff6ff;
  stroke: #0f172a;
  stroke-width: 2;
}

.workflow-node-action-menu {
  position: absolute;
  z-index: 5;
  display: grid;
  gap: 4px;
  padding: 6px;
  overflow-y: auto;
  border: 1px solid #d8dee8;
  border-radius: 6px;
  background: #ffffff;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.16);
}

.workflow-node-action-menu-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-height: 32px;
  width: 100%;
  padding: 6px 10px;
  border: 0;
  border-radius: 4px;
  background: transparent;
  color: #334155;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.workflow-node-action-menu-item span {
  min-width: 0;
  overflow-wrap: anywhere;
}

.workflow-node-action-menu-item small {
  flex: 0 0 auto;
  color: #94a3b8;
}

.workflow-node-action-menu-item:hover,
.workflow-node-action-menu-item:focus-visible {
  outline: none;
  background: #eff6ff;
  color: #1d4ed8;
}

.workflow-node-action-menu-item.inactive {
  color: #94a3b8;
}
.workflow-readonly-summary {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #f8fafc;
}

.workflow-readonly-summary div {
  display: grid;
  grid-template-columns: 72px minmax(0, 1fr);
  gap: 8px;
  font-size: 12px;
}

.workflow-readonly-summary span {
  color: #64748b;
}

.workflow-readonly-summary strong {
  min-width: 0;
  color: #334155;
  overflow-wrap: anywhere;
}

.workflow-advanced-warning {
  margin-bottom: 12px;
}

.workflow-advanced-entry {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.workflow-advanced-entry span {
  color: #64748b;
  font-size: 12px;
}

</style>
