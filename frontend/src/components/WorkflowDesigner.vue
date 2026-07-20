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
        <el-button size="small" @click="organizeLayout">整理布局</el-button>
        <el-button size="small" @click="fitToContent">适应视图</el-button>
        <el-button size="small" @click="resetViewport">回到原点</el-button>
        <el-button size="small" :loading="loading" @click="applyTemplate">套用模板</el-button>
        <el-button size="small" type="primary" :loading="saving" @click="saveGraph">保存流程图</el-button>
      </div>
    </header>

    <div class="workflow-designer-main">
      <div
        class="workflow-canvas"
        :class="{ panning: viewportDrag.active }"
        :style="canvasGridStyle"
      >
        <svg
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
              <path :d="edge.path" />
              <rect :x="edge.labelX - 40" :y="edge.labelY - 13" width="80" height="26" rx="5" />
              <text :x="edge.labelX" :y="edge.labelY + 4">{{ edge.transition.action_name }}</text>
            </g>
            <g
              v-for="state in states"
              :key="state.id"
              class="workflow-node"
              :class="{
                selected: isSelectedState(state),
                terminal: state.category === 'terminal',
                inactive: state.enabled === false
              }"
              :transform="`translate(${state.x}, ${state.y})`"
              @mousedown.stop.prevent="startDrag(state, $event)"
              @click.stop="selectState(state)"
            >
              <rect :fill="state.enabled === false ? '#ffffff' : (state.color || '#2563eb')" width="118" height="42" rx="6" />
              <text x="59" :y="state.enabled === false ? 19 : 26">{{ state.status_name }}</text>
              <text v-if="state.enabled === false" class="workflow-node-status" x="59" y="34">已停用</text>
            </g>
            <g
              v-for="action in nodeActionViews"
              :key="action.key"
              class="workflow-node-action"
              :class="{ selected: isSelectedTransition(action.transition) }"
              :transform="`translate(${action.x}, ${action.y})`"
              role="button"
              tabindex="0"
              @click.stop="selectTransition(action.transition)"
              @keydown.enter.prevent="selectTransition(action.transition)"
              @keydown.space.prevent="selectTransition(action.transition)"
            >
              <rect :width="action.width" :height="action.height" rx="4" />
              <text :x="action.width / 2" :y="action.height / 2 + 4">{{ action.transition.action_name }}</text>
            </g>
          </g>
        </svg>
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
  applyWorkflowDefinitionTemplate,
  createWorkflowDefinition,
  fetchWorkflowDefinitionGraph,
  fetchWorkflowDefinitions,
  saveWorkflowDefinitionGraph
} from '../api/workflowDefinitions'
import { layoutWorkflowNodes } from '../utils/workflowAutoLayout'
import { projectWorkflowCanvas } from '../utils/workflowCanvasProjection'
import { combineWorkflowDragViews } from '../utils/workflowDragViews'
import { buildWorkflowEdgePreviewViews, buildWorkflowEdgeViews } from '../utils/workflowEdgePath'
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
const activeObjectType = ref('requirement')
const definition = ref(null)
const states = ref([])
const transitions = ref([])
const initialStateId = ref(null)
const selectedKind = ref('')
const selectedKey = ref('')
const loading = ref(false)
const saving = ref(false)
const advancedDrawer = ref(null)
const advancedDrawerVisible = ref(false)
const suppressCanvasClamp = ref(false)
const viewportOffset = reactive({ x: 0, y: 0 })
const dragging = reactive({
  state: null,
  startX: 0,
  startY: 0,
  originX: 0,
  originY: 0,
  edgeViews: [],
  canvasEdges: []
})
const viewportDrag = reactive({ active: false, startX: 0, startY: 0, originX: 0, originY: 0 })
const enabledStates = computed(() => states.value.filter((state) => state.enabled))
const canvasProjection = computed(() => projectWorkflowCanvas(states.value, transitions.value))
const fullTransitionViews = computed(() => (
  buildWorkflowEdgeViews(states.value, canvasProjection.value.routedTransitions, transitionKey)
))
const previewTransitionViews = computed(() => (
  buildWorkflowEdgePreviewViews(states.value, canvasProjection.value.routedTransitions, transitionKey)
))
const transitionViews = computed(() => dragging.state
  ? combineWorkflowDragViews(dragging.edgeViews, previewTransitionViews.value, dragging.state.id)
  : fullTransitionViews.value)
const canvasEdgeViews = computed(() => dragging.state ? dragging.canvasEdges : fullTransitionViews.value)
const nodeActionViews = computed(() => states.value.flatMap((state) => (
  (canvasProjection.value.stateActionsByStateId.get(state.id) || []).map((transition, index) => ({
    key: transitionKey(transition),
    transition,
    x: state.x + 19,
    y: state.y + 50 + index * 30,
    width: 80,
    height: 24
  }))
)))
const nodeActionBounds = computed(() => nodeActionViews.value.map((action) => ({
  left: action.x,
  top: action.y,
  right: action.x + action.width,
  bottom: action.y + action.height
})))
const canvasSize = computed(() => (
  workflowCanvasSize(states.value, minimumCanvas, undefined, canvasEdgeViews.value, nodeActionBounds.value)
))

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

watch(canvasSize, (nextCanvas) => {
  if (dragging.state || suppressCanvasClamp.value) return
  clampCurrentViewport(nextCanvas)
}, { flush: 'sync' })

watch(() => props.configId, () => loadDefinition())

onBeforeRouteLeave(async () => confirmDiscardAdvancedDraft())

onMounted(() => {
  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
  window.addEventListener('mousemove', onViewportDrag)
  window.addEventListener('mouseup', stopViewportDrag)
  window.addEventListener('beforeunload', onBeforeUnload)
  loadDefinition()
})

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
  window.removeEventListener('mousemove', onViewportDrag)
  window.removeEventListener('mouseup', stopViewportDrag)
  window.removeEventListener('beforeunload', onBeforeUnload)
})

async function loadDefinition({ discardPendingDraft = true } = {}) {
  if (!props.configId) return
  if (discardPendingDraft && !await confirmDiscardAdvancedDraft()) return
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
  } finally {
    loading.value = false
  }
}

function applyOrganizedLayout() {
  states.value = layoutWorkflowNodes(states.value, transitions.value, initialStateId.value)
}

async function organizeLayout() {
  const result = await requestWorkflowOrganization({
    states: states.value,
    transitions: transitions.value,
    initialStateId: initialStateId.value,
    confirm: () => ElMessageBox.confirm('整理布局将重新排列全部节点，确认继续？', '整理布局', { type: 'warning' }),
    notifyEmpty: () => ElMessage.info('当前没有可整理的状态节点')
  })
  if (!result.organized) return
  states.value = result.states
  fitToContent()
}

function applyGraph(graph, { organize = false } = {}) {
  definition.value = graph.definition || definition.value
  states.value = (graph.states || []).map((item) => ({ ...item }))
  transitions.value = (graph.transitions || []).map((item) => normalizeTransition({
    ...item,
    _client_id: `transition-${item.id}`
  }))
  initialStateId.value = graph.definition?.initial_state_id ?? null
  if (organize) applyOrganizedLayout()
  if (!states.value.length) {
    selectedKind.value = ''
    selectedKey.value = ''
  }
  fitToContent()
}

async function applyTemplate() {
  if (!definition.value?.id) return
  await ElMessageBox.confirm('套用模板会覆盖当前流程图，确认继续？', '套用模板', { type: 'warning' })
  if (!await confirmDiscardAdvancedDraft()) return
  loading.value = true
  try {
    const graph = await applyWorkflowDefinitionTemplate(definition.value.id)
    applyGraph(graph.data, { organize: true })
    ElMessage.success('模板已套用')
  } finally {
    loading.value = false
  }
}

async function changeObjectType(nextObjectType) {
  if (nextObjectType === activeObjectType.value) return
  if (!await confirmDiscardAdvancedDraft()) return
  activeObjectType.value = nextObjectType
  await loadDefinition({ discardPendingDraft: false })
}

async function saveGraph() {
  if (!definition.value?.id) return
  if (transitions.value.some((item) => unsupportedWorkflowConfigSections(item).length)) {
    ElMessage.error('存在未支持的历史配置，请先完成迁移后再保存。')
    return
  }
  saving.value = true
  try {
    const payload = {
      initial_state_id: initialStateId.value,
      states: states.value.map(({ definition_id, ...item }) => item),
      transitions: transitions.value.map((item) => serializeTransition(item))
    }
    const graph = await saveWorkflowDefinitionGraph(definition.value.id, payload)
    applyGraph(graph.data)
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

function selectState(state) {
  selectedKind.value = 'state'
  selectedKey.value = state.id
  advancedDrawerVisible.value = true
  advancedDrawer.value?.open?.()
}

function selectTransition(transition) {
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

async function confirmDiscardAdvancedDraft() {
  if (!advancedDrawer.value?.hasPendingChanges?.()) return true
  return advancedDrawer.value.confirmDiscardPendingChanges()
}

function onBeforeUnload(event) {
  if (!advancedDrawer.value?.hasPendingChanges?.()) return
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

function startDrag(state, event) {
  dragging.edgeViews = [...fullTransitionViews.value]
  dragging.canvasEdges = [...fullTransitionViews.value]
  dragging.state = state
  dragging.startX = event.clientX
  dragging.startY = event.clientY
  dragging.originX = state.x
  dragging.originY = state.y
}

function onDrag(event) {
  if (!dragging.state) return
  dragging.state.x = Math.max(20, Math.min(canvasSize.value.right - 140, dragging.originX + event.clientX - dragging.startX))
  dragging.state.y = Math.max(20, Math.min(canvasSize.value.bottom - 70, dragging.originY + event.clientY - dragging.startY))
}

function clampCurrentViewport(nextCanvas = canvasSize.value) {
  const next = clampViewport({ x: viewportOffset.x, y: viewportOffset.y }, nextCanvas, viewportSize)
  viewportOffset.x = next.x
  viewportOffset.y = next.y
}

function stopDrag() {
  if (!dragging.state) return
  suppressCanvasClamp.value = true
  dragging.state = null
  dragging.edgeViews = []
  dragging.canvasEdges = []
  nextTick(() => {
    suppressCanvasClamp.value = false
  })
}

function startViewportDrag(event) {
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

.workflow-edge path {
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

.workflow-edge.selected path {
  stroke: #1d4ed8;
  stroke-width: 3;
}

.workflow-edge.selected rect {
  stroke: #1d4ed8;
}

.workflow-edge.disabled path {
  stroke: #a8b0bc;
  stroke-dasharray: 7 5;
}

.workflow-edge.disabled rect {
  fill: #f4f6f8;
  stroke-dasharray: 4 3;
}

.workflow-edge.disabled text { fill: #7a8595; }

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

.workflow-node-action {
  cursor: pointer;
  outline: none;
}

.workflow-node-action rect {
  fill: #ffffff;
  stroke: #94a3b8;
  stroke-width: 1;
}

.workflow-node-action text {
  fill: #334155;
  font-size: 12px;
  text-anchor: middle;
  user-select: none;
}

.workflow-node-action:hover rect,
.workflow-node-action:focus-visible rect,
.workflow-node-action.selected rect {
  fill: #eff6ff;
  stroke: #2563eb;
  stroke-width: 2;
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
