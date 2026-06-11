<template>
  <section class="workflow-page">
    <div class="page-head">
      <div>
        <h1>工作流配置</h1>
        <p>通过组件节点配置状态触发关系，例如项目关闭后触发未关闭需求和任务状态变更。</p>
      </div>
      <div class="workflow-head-actions">
        <el-select v-model="selectedTemplateKey" clearable filterable placeholder="选择模板" style="width: 260px" @change="loadTemplate">
          <el-option v-for="template in templates" :key="template.template_key" :label="template.template_name" :value="template.template_key" />
        </el-select>
        <el-button @click="resetDesigner">新建</el-button>
        <el-button type="primary" :loading="saving" @click="saveRule">保存工作流</el-button>
      </div>
    </div>

    <div class="workflow-layout">
      <aside class="workflow-panel workflow-palette">
        <h2>组件</h2>
        <el-tabs v-model="componentTab" stretch>
          <el-tab-pane label="触发" name="trigger" />
          <el-tab-pane label="条件" name="condition" />
          <el-tab-pane label="动作" name="action" />
        </el-tabs>
        <div class="workflow-component-list">
          <button
            v-for="component in filteredComponents"
            :key="component.component_key"
            class="workflow-component"
            draggable="true"
            type="button"
            @click="addNode(component)"
            @dragstart="onComponentDragStart(component)"
          >
            <span :class="['workflow-dot', `workflow-dot--${component.category}`]" />
            <strong>{{ component.label }}</strong>
            <small>{{ component.description }}</small>
          </button>
        </div>
      </aside>

      <main class="workflow-canvas-wrap">
        <div class="workflow-rule-form">
          <el-input v-model="ruleForm.rule_name" placeholder="工作流名称" />
          <el-select v-model="ruleForm.scope_type" style="width: 130px">
            <el-option label="系统默认" value="system" />
            <el-option label="项目级" value="project" />
          </el-select>
          <el-input-number v-model="ruleForm.priority" :min="1" :max="999" />
          <el-switch v-model="ruleForm.enabled" active-text="启用" inactive-text="停用" />
        </div>

        <div class="workflow-canvas" @dragover.prevent @drop="onCanvasDrop">
          <svg class="workflow-lines" :viewBox="`0 0 ${canvasWidth} ${canvasHeight}`" preserveAspectRatio="none">
            <line
              v-for="edge in edgesWithPosition"
              :key="edge.id"
              :x1="edge.x1"
              :y1="edge.y1"
              :x2="edge.x2"
              :y2="edge.y2"
              stroke="#7b8ea8"
              stroke-width="2"
              marker-end="url(#workflow-arrow)"
            />
            <defs>
              <marker id="workflow-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto">
                <path d="M0,0 L0,6 L8,3 z" fill="#7b8ea8" />
              </marker>
            </defs>
          </svg>

          <button
            v-for="node in nodes"
            :key="node.id"
            :class="['workflow-node', `workflow-node--${node.category}`, { active: selectedNodeId === node.id }]"
            :style="{ left: `${node.x}px`, top: `${node.y}px` }"
            type="button"
            draggable="true"
            @click="selectNode(node.id)"
            @dragstart="onNodeDragStart(node, $event)"
            @dragend="onNodeDragEnd(node, $event)"
          >
            <span>{{ categoryLabel(node.category) }}</span>
            <strong>{{ node.label }}</strong>
            <small>{{ node.component_key }}</small>
          </button>

          <el-empty v-if="!nodes.length" description="从左侧拖拽或点击组件添加到工作流" />
        </div>

        <div class="workflow-edge-editor">
          <span>上下级触发关系</span>
          <el-select v-model="edgeForm.source" placeholder="上级节点" clearable style="width: 220px">
            <el-option v-for="node in nodes" :key="node.id" :label="node.label" :value="node.id" />
          </el-select>
          <el-select v-model="edgeForm.target" placeholder="下级节点" clearable style="width: 220px">
            <el-option v-for="node in nodes" :key="node.id" :label="node.label" :value="node.id" />
          </el-select>
          <el-button @click="addEdge">添加关系</el-button>
        </div>
        <div v-if="edgesWithNames.length" class="workflow-edge-list">
          <el-tag v-for="edge in edgesWithNames" :key="edge.id" closable @close="removeEdge(edge.id)">
            {{ edge.sourceLabel }} -> {{ edge.targetLabel }}
          </el-tag>
        </div>
      </main>

      <aside class="workflow-panel workflow-inspector">
        <h2>属性</h2>
        <template v-if="selectedNode">
          <el-form label-position="top">
            <el-form-item label="节点名称"><el-input v-model="selectedNode.label" /></el-form-item>
            <el-form-item v-for="field in selectedComponentSchema" :key="field.field" :label="field.label">
              <el-select v-if="field.type === 'select'" v-model="selectedNode.config[field.field]" clearable filterable>
                <el-option v-if="field.allow_any" label="任意" value="*" />
                <el-option v-for="option in field.options || []" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
              <el-select v-else-if="field.type === 'multi_select'" v-model="selectedNode.config[field.field]" multiple clearable filterable>
                <el-option v-for="option in field.options || []" :key="option.value" :label="option.label" :value="option.value" />
              </el-select>
              <el-input v-else-if="field.type === 'textarea'" v-model="selectedNode.config[field.field]" type="textarea" :rows="3" />
              <el-input v-else v-model="selectedNode.config[field.field]" />
            </el-form-item>
          </el-form>
          <el-button type="danger" plain @click="removeSelectedNode">删除节点</el-button>
        </template>
        <el-empty v-else description="选择节点后配置属性" />

        <h2 class="workflow-side-title">规则列表</h2>
        <div class="workflow-rule-list">
          <button v-for="rule in rules" :key="rule.id" type="button" :class="{ active: rule.id === editingRuleId }" @click="loadRule(rule)">
            <strong>{{ rule.rule_name }}</strong>
            <span>{{ rule.target_object }} / {{ rule.trigger_action }}</span>
          </button>
        </div>
        <el-button v-if="editingRuleId" type="danger" plain @click="removeRule">删除当前规则</el-button>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  createWorkflowRule,
  deleteWorkflowRule,
  fetchWorkflowComponents,
  fetchWorkflowRules,
  fetchWorkflowTemplates,
  updateWorkflowRule
} from '../api/workflowRules'

const canvasWidth = 1120
const canvasHeight = 620
const components = ref([])
const templates = ref([])
const rules = ref([])
const nodes = ref([])
const edges = ref([])
const selectedNodeId = ref(null)
const selectedTemplateKey = ref('')
const componentTab = ref('trigger')
const editingRuleId = ref(null)
const saving = ref(false)
const draggedComponent = ref(null)
const draggedNode = ref(null)
const ruleForm = reactive({ rule_name: '', scope_type: 'system', priority: 100, enabled: true, description: '' })
const edgeForm = reactive({ source: null, target: null })

const filteredComponents = computed(() => components.value.filter((item) => item.category === componentTab.value))
const selectedNode = computed(() => nodes.value.find((node) => node.id === selectedNodeId.value))
const selectedComponentSchema = computed(() => components.value.find((item) => item.component_key === selectedNode.value?.component_key)?.config_schema || [])
const edgesWithPosition = computed(() => edges.value.map((edge) => {
  const source = nodes.value.find((node) => node.id === edge.source)
  const target = nodes.value.find((node) => node.id === edge.target)
  if (!source || !target) return null
  return { ...edge, x1: source.x + 180, y1: source.y + 44, x2: target.x, y2: target.y + 44 }
}).filter(Boolean))
const edgesWithNames = computed(() => edges.value.map((edge) => {
  const source = nodes.value.find((node) => node.id === edge.source)
  const target = nodes.value.find((node) => node.id === edge.target)
  if (!source || !target) return null
  return { ...edge, sourceLabel: source.label, targetLabel: target.label }
}).filter(Boolean))

function categoryLabel(category) {
  return { trigger: '触发', condition: '条件', action: '动作' }[category] || category
}

function onComponentDragStart(component) {
  draggedComponent.value = component
}

function onCanvasDrop(event) {
  if (!draggedComponent.value) return
  const rect = event.currentTarget.getBoundingClientRect()
  addNode(draggedComponent.value, event.clientX - rect.left, event.clientY - rect.top)
  draggedComponent.value = null
}

function addNode(component, x = null, y = null) {
  const index = nodes.value.length
  const node = {
    id: `node-${Date.now()}-${index}`,
    component_key: component.component_key,
    category: component.category,
    label: component.label,
    x: x ?? 80 + index * 32,
    y: y ?? 80 + index * 96,
    config: defaultConfig(component)
  }
  nodes.value.push(node)
  selectedNodeId.value = node.id
}

function defaultConfig(component) {
  const config = {}
  for (const field of component.config_schema || []) {
    if (field.type === 'multi_select') config[field.field] = []
    else if (field.allow_any) config[field.field] = '*'
    else config[field.field] = ''
  }
  return config
}

function selectNode(id) {
  selectedNodeId.value = id
}

function onNodeDragStart(node, event) {
  draggedNode.value = { id: node.id, offsetX: event.offsetX, offsetY: event.offsetY }
}

function onNodeDragEnd(node, event) {
  if (!draggedNode.value) return
  const canvas = document.querySelector('.workflow-canvas')
  const rect = canvas.getBoundingClientRect()
  node.x = Math.max(16, Math.min(canvasWidth - 210, event.clientX - rect.left - draggedNode.value.offsetX))
  node.y = Math.max(16, Math.min(canvasHeight - 100, event.clientY - rect.top - draggedNode.value.offsetY))
  draggedNode.value = null
}

function addEdge() {
  if (!edgeForm.source || !edgeForm.target) return ElMessage.warning('请选择上下级节点')
  if (edgeForm.source === edgeForm.target) return ElMessage.warning('上下级节点不能相同')
  if (edges.value.some((edge) => edge.source === edgeForm.source && edge.target === edgeForm.target)) return ElMessage.warning('关系已存在')
  if (createsCycle(edgeForm.source, edgeForm.target)) return ElMessage.warning('上下级关系不能形成循环')
  edges.value.push({ id: `edge-${Date.now()}`, source: edgeForm.source, target: edgeForm.target })
  Object.assign(edgeForm, { source: null, target: null })
}

function createsCycle(sourceId, targetId) {
  const nextMap = new Map()
  for (const edge of edges.value) {
    if (!nextMap.has(edge.source)) nextMap.set(edge.source, [])
    nextMap.get(edge.source).push(edge.target)
  }
  if (!nextMap.has(sourceId)) nextMap.set(sourceId, [])
  nextMap.get(sourceId).push(targetId)

  const visited = new Set()
  const stack = [targetId]
  while (stack.length) {
    const current = stack.pop()
    if (current === sourceId) return true
    if (visited.has(current)) continue
    visited.add(current)
    stack.push(...(nextMap.get(current) || []))
  }
  return false
}

function removeEdge(edgeId) {
  edges.value = edges.value.filter((edge) => edge.id !== edgeId)
}

function removeSelectedNode() {
  if (!selectedNode.value) return
  nodes.value = nodes.value.filter((node) => node.id !== selectedNode.value.id)
  edges.value = edges.value.filter((edge) => edge.source !== selectedNode.value.id && edge.target !== selectedNode.value.id)
  selectedNodeId.value = null
}

function resetDesigner() {
  editingRuleId.value = null
  selectedTemplateKey.value = ''
  Object.assign(ruleForm, { rule_name: '', scope_type: 'system', priority: 100, enabled: true, description: '' })
  nodes.value = []
  edges.value = []
  selectedNodeId.value = null
}

function loadTemplate(templateKey) {
  const template = templates.value.find((item) => item.template_key === templateKey)
  if (!template) return
  editingRuleId.value = null
  Object.assign(ruleForm, {
    rule_name: template.template_name,
    scope_type: 'system',
    priority: 100,
    enabled: true,
    description: template.description
  })
  nodes.value = clone(template.condition_json.nodes || [])
  edges.value = clone(template.condition_json.edges || [])
  selectedNodeId.value = nodes.value[0]?.id || null
}

function loadRule(rule) {
  editingRuleId.value = rule.id
  selectedTemplateKey.value = ''
  Object.assign(ruleForm, {
    rule_name: rule.rule_name,
    scope_type: rule.scope_type,
    priority: rule.priority,
    enabled: rule.enabled,
    description: rule.description || ''
  })
  nodes.value = clone(rule.condition_json?.nodes || [])
  edges.value = clone(rule.condition_json?.edges || [])
  selectedNodeId.value = nodes.value[0]?.id || null
}

async function saveRule() {
  if (!ruleForm.rule_name.trim()) return ElMessage.warning('请填写工作流名称')
  if (!nodes.value.length) return ElMessage.warning('请至少添加一个节点')
  const trigger = nodes.value.find((node) => node.category === 'trigger')
  if (!trigger) return ElMessage.warning('请添加触发节点')
  saving.value = true
  try {
    const payload = buildPayload(trigger)
    if (editingRuleId.value) await updateWorkflowRule(editingRuleId.value, payload)
    else {
      const created = await createWorkflowRule(payload)
      editingRuleId.value = created.data.id
    }
    await loadData()
    ElMessage.success('工作流已保存')
  } finally {
    saving.value = false
  }
}

function buildPayload(trigger) {
  const relations = edges.value.map((edge) => {
    const source = nodes.value.find((node) => node.id === edge.source)
    const target = nodes.value.find((node) => node.id === edge.target)
    return {
      source: edge.source,
      source_component: source?.component_key || '',
      target: edge.target,
      target_component: target?.component_key || ''
    }
  })
  const conditionJson = { designer_version: 1, nodes: nodes.value, edges: edges.value, relations }
  const actionJson = {
    trigger: {
      target_object: targetObjectFromTrigger(trigger.component_key),
      trigger_action: triggerActionFromComponent(trigger.component_key),
      config: trigger.config
    },
    relations,
    steps: nodes.value.filter((node) => node.id !== trigger.id).map((node) => ({
      id: node.id,
      type: node.category,
      component_key: node.component_key,
      config: node.config
    }))
  }
  return {
    ...ruleForm,
    target_object: actionJson.trigger.target_object,
    trigger_action: actionJson.trigger.trigger_action,
    condition_json: conditionJson,
    action_json: actionJson
  }
}

function targetObjectFromTrigger(componentKey) {
  if (componentKey.startsWith('project_')) return 'project'
  if (componentKey.startsWith('program_')) return 'program'
  if (componentKey.startsWith('iteration_')) return 'iteration'
  if (componentKey.startsWith('requirement_')) return 'requirement'
  if (componentKey.startsWith('task_')) return 'task'
  if (componentKey.startsWith('bug_')) return 'bug'
  if (componentKey.startsWith('test_case_')) return 'test_case'
  return 'object'
}

function triggerActionFromComponent(componentKey) {
  if (componentKey.includes('status_changed')) return 'status_changed'
  if (componentKey.includes('result_changed')) return 'execution_result_changed'
  if (componentKey.includes('field_changed')) return 'field_changed'
  return 'triggered'
}

async function removeRule() {
  if (!editingRuleId.value) return
  await ElMessageBox.confirm('确认删除当前工作流规则？', '提示', { type: 'warning' })
  await deleteWorkflowRule(editingRuleId.value)
  resetDesigner()
  await loadData()
}

async function loadData() {
  const [componentRes, templateRes, ruleRes] = await Promise.all([
    fetchWorkflowComponents(),
    fetchWorkflowTemplates(),
    fetchWorkflowRules()
  ])
  components.value = componentRes.data
  templates.value = templateRes.data
  rules.value = ruleRes.data
}

function clone(value) {
  return JSON.parse(JSON.stringify(value))
}

onMounted(loadData)
</script>

<style scoped>
.workflow-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

.workflow-head-actions,
.workflow-rule-form,
.workflow-edge-editor,
.workflow-edge-list {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.workflow-layout {
  display: grid;
  grid-template-columns: 260px minmax(540px, 1fr) 300px;
  gap: 12px;
  flex: 1 1 auto;
  min-height: 0;
}

.workflow-panel,
.workflow-canvas-wrap {
  min-width: 0;
  min-height: 0;
  background: #ffffff;
  border: 1px solid #d9e2ef;
  border-radius: 6px;
}

.workflow-panel {
  display: flex;
  flex-direction: column;
  padding: 12px;
  overflow: hidden;
}

.workflow-panel h2 {
  margin: 0 0 10px;
  color: #17213a;
  font-size: 16px;
}

.workflow-component-list,
.workflow-rule-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
  overflow-y: auto;
  padding-right: 4px;
}

.workflow-component {
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr);
  gap: 4px 8px;
  width: 100%;
  padding: 10px;
  text-align: left;
  background: #f7f9fc;
  border: 1px solid #dce5f0;
  border-radius: 6px;
  cursor: grab;
}

.workflow-component:hover {
  border-color: #2f80ed;
  box-shadow: 0 2px 8px rgba(47, 128, 237, .12);
}

.workflow-component strong,
.workflow-rule-list strong {
  overflow: hidden;
  color: #17213a;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workflow-component small,
.workflow-rule-list span {
  grid-column: 2;
  color: #667085;
  font-size: 12px;
  line-height: 1.45;
}

.workflow-dot {
  width: 9px;
  height: 9px;
  margin-top: 5px;
  border-radius: 50%;
}

.workflow-dot--trigger {
  background: #2f80ed;
}

.workflow-dot--condition {
  background: #d98a00;
}

.workflow-dot--action {
  background: #16845f;
}

.workflow-canvas-wrap {
  display: flex;
  flex-direction: column;
  padding: 12px;
  overflow: hidden;
}

.workflow-rule-form {
  flex: 0 0 auto;
  margin-bottom: 10px;
}

.workflow-canvas {
  position: relative;
  flex: 1 1 auto;
  min-height: 420px;
  overflow: auto;
  background:
    linear-gradient(#edf2f8 1px, transparent 1px),
    linear-gradient(90deg, #edf2f8 1px, transparent 1px),
    #fbfdff;
  background-size: 24px 24px;
  border: 1px solid #d9e2ef;
  border-radius: 6px;
}

.workflow-lines {
  position: absolute;
  inset: 0;
  width: 1120px;
  height: 620px;
  pointer-events: none;
}

.workflow-node {
  position: absolute;
  display: grid;
  gap: 3px;
  width: 190px;
  min-height: 78px;
  padding: 10px 12px;
  text-align: left;
  background: #ffffff;
  border: 2px solid #9eb2c9;
  border-radius: 6px;
  box-shadow: 0 6px 18px rgba(31, 45, 61, .12);
  cursor: move;
}

.workflow-node.active {
  border-color: #2f80ed;
  box-shadow: 0 0 0 3px rgba(47, 128, 237, .16);
}

.workflow-node--trigger {
  border-color: #2f80ed;
}

.workflow-node--condition {
  border-color: #d98a00;
}

.workflow-node--action {
  border-color: #16845f;
}

.workflow-node span {
  color: #667085;
  font-size: 12px;
}

.workflow-node strong {
  color: #17213a;
  font-size: 15px;
}

.workflow-node small {
  overflow: hidden;
  color: #8a94a6;
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workflow-edge-editor {
  flex-wrap: wrap;
  flex: 0 0 auto;
  padding-top: 10px;
}

.workflow-edge-editor > span {
  color: #344054;
  font-weight: 700;
}

.workflow-edge-list {
  flex-wrap: wrap;
  padding-top: 8px;
}

.workflow-inspector :deep(.el-form-item) {
  margin-bottom: 12px;
}

.workflow-side-title {
  padding-top: 16px;
  margin-top: 16px !important;
  border-top: 1px solid #e4eaf2;
}

.workflow-rule-list {
  margin-bottom: 10px;
}

.workflow-rule-list button {
  display: grid;
  gap: 4px;
  width: 100%;
  padding: 9px 10px;
  text-align: left;
  background: #f7f9fc;
  border: 1px solid #dce5f0;
  border-radius: 6px;
  cursor: pointer;
}

.workflow-rule-list button.active {
  background: #ecf4ff;
  border-color: #2f80ed;
}

@media (max-width: 1200px) {
  .workflow-layout {
    grid-template-columns: 230px minmax(480px, 1fr);
  }

  .workflow-inspector {
    grid-column: 1 / -1;
    max-height: 280px;
  }
}

@media (max-width: 820px) {
  .workflow-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .workflow-palette {
    max-height: 260px;
  }

  .workflow-head-actions,
  .workflow-rule-form {
    flex-wrap: wrap;
  }
}
</style>
