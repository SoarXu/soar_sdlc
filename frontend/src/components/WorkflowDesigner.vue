<template>
  <div class="workflow-designer">
    <header class="workflow-designer-toolbar">
      <div>
        <h3>可视化工作流</h3>
        <p>拖拽状态节点，按住空白画布移动视角，点击节点或连线进行配置。</p>
      </div>
      <div class="workflow-designer-actions">
        <el-select v-model="activeObjectType" size="small" class="workflow-object-select" @change="loadDefinition">
          <el-option v-for="item in objectTypes" :key="item.value" :label="item.label" :value="item.value" />
        </el-select>
        <el-button size="small" @click="addState">新增状态</el-button>
        <el-button size="small" @click="addTransition">新增流转</el-button>
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
            <marker id="workflow-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#94a3b8" />
            </marker>
          </defs>
          <g :transform="`translate(${viewportOffset.x}, ${viewportOffset.y})`">
            <g v-for="edge in transitionViews" :key="edge.key" class="workflow-edge" :class="{ selected: isSelectedTransition(edge.transition) }" @click.stop="selectTransition(edge.transition)">
              <path :d="edge.path" />
              <rect :x="edge.labelX - 40" :y="edge.labelY - 13" width="80" height="26" rx="5" />
              <text :x="edge.labelX" :y="edge.labelY + 4">{{ edge.transition.action_name }}</text>
            </g>
            <g
              v-for="state in states"
              :key="state.status_key"
              class="workflow-node"
              :class="{ selected: isSelectedState(state), terminal: state.category === 'terminal' }"
              :transform="`translate(${state.x}, ${state.y})`"
              @mousedown.stop.prevent="startDrag(state, $event)"
              @click.stop="selectState(state)"
            >
              <rect :fill="state.color || '#2563eb'" width="118" height="42" rx="6" />
              <text x="59" y="26">{{ state.status_name }}</text>
            </g>
          </g>
        </svg>
      </div>

      <aside class="workflow-config-panel">
        <template v-if="selectedState">
          <h3>状态配置</h3>
          <el-form label-position="top">
            <el-form-item label="状态名称"><el-input v-model="selectedState.status_name" /></el-form-item>
            <el-form-item label="状态值"><el-input v-model="selectedState.status_key" /></el-form-item>
            <el-form-item label="状态类型">
              <el-select v-model="selectedState.category">
                <el-option label="开始" value="start" />
                <el-option label="普通" value="normal" />
                <el-option label="终态" value="terminal" />
              </el-select>
            </el-form-item>
            <el-form-item label="颜色"><el-color-picker v-model="selectedState.color" /></el-form-item>
            <el-form-item label="启用"><el-switch v-model="selectedState.enabled" /></el-form-item>
            <el-button type="danger" plain @click="removeSelectedState">删除状态</el-button>
          </el-form>
        </template>

        <template v-else-if="selectedTransition">
          <h3>流转配置</h3>
          <el-form label-position="top">
            <el-form-item label="动作名称"><el-input v-model="selectedTransition.action_name" /></el-form-item>
            <el-form-item label="动作值"><el-input v-model="selectedTransition.action_key" /></el-form-item>
            <el-form-item label="来源状态">
              <el-select v-model="selectedTransition.from_status">
                <el-option v-for="state in states" :key="state.status_key" :label="state.status_name" :value="state.status_key" />
              </el-select>
            </el-form-item>
            <el-form-item label="目标状态">
              <el-select v-model="selectedTransition.to_status">
                <el-option v-for="state in states" :key="state.status_key" :label="state.status_name" :value="state.status_key" />
              </el-select>
            </el-form-item>
            <el-form-item label="允许角色"><el-select v-model="selectedTransition.allowed_role_list" multiple filterable>
              <el-option v-for="role in roleOptions" :key="role.value" :label="role.label" :value="role.value" />
            </el-select></el-form-item>
            <el-form-item label="下一处理人">
              <el-select v-model="selectedTransition.handler_rule.target_type">
                <el-option v-for="item in targetTypes" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="目标角色">
              <el-select v-model="selectedTransition.handler_target_roles" multiple filterable :disabled="selectedTransition.handler_rule.target_type !== 'project_role'">
                <el-option v-for="role in roleOptions" :key="role.value" :label="role.label" :value="role.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="兜底策略">
              <el-select v-model="selectedTransition.handler_rule.fallback_type">
                <el-option label="保持当前处理人" value="keep_current" />
                <el-option label="按项目角色" value="project_role" />
                <el-option label="置为空" value="none" />
              </el-select>
            </el-form-item>
            <el-form-item label="兜底角色">
              <el-select v-model="selectedTransition.handler_fallback_roles" multiple filterable :disabled="selectedTransition.handler_rule.fallback_type !== 'project_role'">
                <el-option v-for="role in roleOptions" :key="role.value" :label="role.label" :value="role.value" />
              </el-select>
            </el-form-item>
            <el-form-item label="启用"><el-switch v-model="selectedTransition.enabled" /></el-form-item>
            <el-button type="danger" plain @click="removeSelectedTransition">删除流转</el-button>
          </el-form>
        </template>

        <el-empty v-else description="选择状态或流转进行配置" />
      </aside>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  applyWorkflowDefinitionTemplate,
  createWorkflowDefinition,
  fetchWorkflowDefinitionGraph,
  fetchWorkflowDefinitions,
  saveWorkflowDefinitionGraph
} from '../api/workflowDefinitions'
import { buildWorkflowEdgeView } from '../utils/workflowEdgePath'
import {
  applyPanDelta,
  clampViewport,
  fitViewportToNodes
} from '../utils/workflowViewport'

const props = defineProps({
  configId: { type: Number, required: true },
  configName: { type: String, default: '' },
  roleOptions: { type: Array, default: () => [] }
})

const objectTypes = [
  { label: '需求', value: 'requirement' },
  { label: '任务', value: 'task' },
  { label: 'Bug', value: 'bug' }
]
const targetTypes = [
  { label: '项目角色', value: 'project_role' },
  { label: '保持当前处理人', value: 'keep_current' },
  { label: '需求提出人', value: 'proposer' },
  { label: 'Bug 报告人', value: 'reporter' },
  { label: '上次修复人', value: 'last_resolver' },
  { label: '无处理人', value: 'none' }
]
const canvas = { width: 2400, height: 1400 }
const viewportSize = { width: 980, height: 540 }
const activeObjectType = ref('requirement')
const definition = ref(null)
const states = ref([])
const transitions = ref([])
const selectedKind = ref('')
const selectedKey = ref('')
const loading = ref(false)
const saving = ref(false)
const viewportOffset = reactive({ x: 0, y: 0 })
const dragging = reactive({ state: null, startX: 0, startY: 0, originX: 0, originY: 0 })
const viewportDrag = reactive({ active: false, startX: 0, startY: 0, originX: 0, originY: 0 })

const selectedState = computed(() => selectedKind.value === 'state' ? states.value.find((item) => item.status_key === selectedKey.value) : null)
const selectedTransition = computed(() => selectedKind.value === 'transition' ? transitions.value.find((item) => transitionKey(item) === selectedKey.value) : null)
const canvasGridStyle = computed(() => ({
  backgroundPosition: `${viewportOffset.x}px ${viewportOffset.y}px`
}))
const transitionViews = computed(() => transitions.value.map((transition) => {
  const from = states.value.find((item) => item.status_key === transition.from_status)
  const to = states.value.find((item) => item.status_key === transition.to_status)
  if (!from || !to) return null
  return { key: transitionKey(transition), transition, ...buildWorkflowEdgeView(from, to) }
}).filter(Boolean))

watch(() => props.configId, () => loadDefinition())

onMounted(() => {
  window.addEventListener('mousemove', onDrag)
  window.addEventListener('mouseup', stopDrag)
  window.addEventListener('mousemove', onViewportDrag)
  window.addEventListener('mouseup', stopViewportDrag)
  loadDefinition()
})

onBeforeUnmount(() => {
  window.removeEventListener('mousemove', onDrag)
  window.removeEventListener('mouseup', stopDrag)
  window.removeEventListener('mousemove', onViewportDrag)
  window.removeEventListener('mouseup', stopViewportDrag)
})

async function loadDefinition() {
  if (!props.configId) return
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

function applyGraph(graph) {
  states.value = (graph.states || []).map((item) => ({ ...item }))
  transitions.value = (graph.transitions || []).map(normalizeTransition)
  if (!states.value.length) {
    selectedKind.value = ''
    selectedKey.value = ''
  }
  fitToContent()
}

async function applyTemplate() {
  if (!definition.value?.id) return
  await ElMessageBox.confirm('套用模板会覆盖当前流程图，确认继续？', '套用模板', { type: 'warning' })
  loading.value = true
  try {
    const graph = await applyWorkflowDefinitionTemplate(definition.value.id)
    applyGraph(graph.data)
    ElMessage.success('模板已套用')
  } finally {
    loading.value = false
  }
}

async function saveGraph() {
  if (!definition.value?.id) return
  saving.value = true
  try {
    const payload = {
      states: states.value.map(({ id, definition_id, ...item }) => item),
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
  const statusKey = `state_${index}`
  states.value.push({
    status_key: statusKey,
    status_name: `状态${index}`,
    category: 'normal',
    color: '#2563eb',
    x: 120 + (index % 4) * 180,
    y: 90 + Math.floor(index / 4) * 120,
    sort_order: index * 10,
    enabled: true
  })
  selectedKind.value = 'state'
  selectedKey.value = statusKey
}

function addTransition() {
  if (states.value.length < 2) {
    ElMessage.warning('至少需要两个状态')
    return
  }
  const from = states.value[0]
  const to = states.value[1]
  const transition = normalizeTransition({
    action_key: `action_${transitions.value.length + 1}`,
    action_name: `流转${transitions.value.length + 1}`,
    from_status: from.status_key,
    to_status: to.status_key,
    allowed_roles: '',
    handler_rule: { target_type: 'keep_current', target_roles: '', fallback_type: 'keep_current', fallback_roles: '' },
    enabled: true,
    sort_order: (transitions.value.length + 1) * 10
  })
  transitions.value.push(transition)
  selectTransition(transition)
}

function selectState(state) {
  selectedKind.value = 'state'
  selectedKey.value = state.status_key
}

function selectTransition(transition) {
  selectedKind.value = 'transition'
  selectedKey.value = transitionKey(transition)
}

function clearSelection() {
  selectedKind.value = ''
  selectedKey.value = ''
}

function removeSelectedState() {
  if (!selectedState.value) return
  const key = selectedState.value.status_key
  if (transitions.value.some((item) => item.from_status === key || item.to_status === key)) {
    ElMessage.warning('请先删除引用该状态的流转')
    return
  }
  states.value = states.value.filter((item) => item.status_key !== key)
  clearSelection()
}

function removeSelectedTransition() {
  if (!selectedTransition.value) return
  const key = transitionKey(selectedTransition.value)
  transitions.value = transitions.value.filter((item) => transitionKey(item) !== key)
  clearSelection()
}

function startDrag(state, event) {
  dragging.state = state
  dragging.startX = event.clientX
  dragging.startY = event.clientY
  dragging.originX = state.x
  dragging.originY = state.y
}

function onDrag(event) {
  if (!dragging.state) return
  dragging.state.x = Math.max(20, Math.min(canvas.width - 140, dragging.originX + event.clientX - dragging.startX))
  dragging.state.y = Math.max(20, Math.min(canvas.height - 70, dragging.originY + event.clientY - dragging.startY))
}

function stopDrag() {
  dragging.state = null
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
    canvas,
    viewportSize
  )
  viewportOffset.x = next.x
  viewportOffset.y = next.y
}

function stopViewportDrag() {
  viewportDrag.active = false
}

function fitToContent() {
  const next = fitViewportToNodes(states.value, canvas, viewportSize)
  viewportOffset.x = next.x
  viewportOffset.y = next.y
}

function resetViewport() {
  const next = clampViewport({ x: 0, y: 0 }, canvas, viewportSize)
  viewportOffset.x = next.x
  viewportOffset.y = next.y
}

function isSelectedState(state) {
  return selectedKind.value === 'state' && selectedKey.value === state.status_key
}

function isSelectedTransition(transition) {
  return selectedKind.value === 'transition' && selectedKey.value === transitionKey(transition)
}

function transitionKey(transition) {
  return `${transition.action_key}:${transition.from_status}:${transition.to_status}`
}

function normalizeTransition(item) {
  const handlerRule = item.handler_rule || { target_type: 'keep_current', target_roles: '', fallback_type: 'keep_current', fallback_roles: '' }
  return {
    ...item,
    handler_rule: {
      target_type: handlerRule.target_type || 'keep_current',
      target_roles: roleArray(handlerRule.target_roles).join(','),
      fallback_type: handlerRule.fallback_type || 'keep_current',
      fallback_roles: roleArray(handlerRule.fallback_roles).join(',')
    },
    allowed_role_list: roleArray(item.allowed_roles),
    handler_target_roles: roleArray(handlerRule.target_roles),
    handler_fallback_roles: roleArray(handlerRule.fallback_roles)
  }
}

function serializeTransition(item) {
  const { id, definition_id, allowed_role_list, handler_target_roles, handler_fallback_roles, ...rest } = item
  return {
    ...rest,
    allowed_roles: allowed_role_list.join(','),
    handler_rule: {
      ...rest.handler_rule,
      target_roles: handler_target_roles.join(','),
      fallback_roles: handler_fallback_roles.join(',')
    }
  }
}

function roleArray(value) {
  if (Array.isArray(value)) return value
  return String(value || '').split(',').map((item) => item.trim()).filter(Boolean)
}
</script>

<style scoped>
.workflow-designer {
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

.workflow-designer-main {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
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

.workflow-config-panel {
  border-left: 1px solid #e5e7eb;
  padding: 16px;
  background: #ffffff;
  overflow: auto;
}

.workflow-config-panel h3 {
  margin: 0 0 14px;
  font-size: 16px;
  color: #0f172a;
}

@media (max-width: 1100px) {
  .workflow-designer-main {
    grid-template-columns: 1fr;
  }

  .workflow-config-panel {
    border-left: 0;
    border-top: 1px solid #e5e7eb;
  }
}
</style>
