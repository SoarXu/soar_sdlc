import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'

const componentPath = fileURLToPath(new URL('./WorkflowDesigner.vue', import.meta.url))
const source = await readFile(componentPath, 'utf8')

function functionBody(name, nextName) {
  const start = source.indexOf(`function ${name}`)
  assert.notEqual(start, -1, `missing function ${name}`)
  const end = nextName ? source.indexOf(`function ${nextName}`, start) : source.length
  assert.notEqual(end, -1, `missing boundary function ${nextName}`)
  return source.slice(start, end)
}

assert.doesNotMatch(source, /import \{ layoutWorkflowNodes \} from '\.\.\/utils\/workflowAutoLayout'/)
assert.match(source, /import \{ layoutWorkflowWithElk \} from '\.\.\/utils\/workflowElkLayout'/)
assert.match(source, /import \{ workflowGraphSnapshot \} from '\.\.\/utils\/workflowGraphSnapshot'/)
assert.match(
  source,
  /import \{ buildWorkflowEdgeViews \} from '\.\.\/utils\/workflowEdgePath'/
)
assert.match(source, /import \{ requestWorkflowOrganization \} from '\.\.\/utils\/workflowLayoutInteraction'/)
assert.match(source, /import \{ projectWorkflowCanvas \} from '\.\.\/utils\/workflowCanvasProjection'/)
assert.doesNotMatch(source, /combineWorkflowDragViews/)
assert.doesNotMatch(source, /buildWorkflowEdgePreviewViews/)
assert.match(source, /workflowCanvasSize/)
assert.match(source, /createManualDiagramConfig/)
assert.match(source, /moveManualAnchor/)
assert.match(source, /moveManualSegment/)
assert.match(source, /isManualDiagramRoute/)
assert.match(source, /applyGeneratedRoutesFromViews[\s\S]*createWorkflowDragFrame[\s\S]*from '\.\.\/utils\/workflowDragFrame'/)
assert.doesNotMatch(source, /\bbuildWorkflowEdgeView\b/)
assert.match(
  source,
  /const canvasProjection = computed\(\(\) => projectWorkflowCanvas\(states\.value, transitions\.value\)\)/
)
assert.match(
  source,
  /buildWorkflowEdgeViews\(states\.value, canvasProjection\.value\.routedTransitions, transitionKey\)/
)
assert.match(source, /const dragFrame = ref\(null\)/)
assert.match(source, /const renderedStates = computed\(\(\) => dragFrame\.value\?\.states \|\| states\.value\)/)
assert.match(
  source,
  /const transitionViews = computed\(\(\) => dragFrame\.value\?\.transitionViews \|\| fullTransitionViews\.value\)/
)
assert.match(source, /const minimumCanvas = \{ width: 2400, height: 1400 \}/)
assert.match(
  source,
  /const canvasEdgeViews = computed\(\(\) => transitionViews\.value\)/
)
assert.match(
  source,
  /workflowCanvasSize\(renderedStates\.value, minimumCanvas, undefined, canvasEdgeViews\.value\)/
)
assert.match(source, /v-for="edge in transitionViews"/)
assert.match(source, /v-for="state in renderedStates"/)
assert.match(source, /@click\.stop="handleStateClick\(state\)"/)
assert.match(source, /class="workflow-node-action-badge"/)
assert.match(source, /:aria-label="nodeActionAriaLabel\(state\)"/)
assert.match(source, /@click\.stop="toggleNodeActionMenu\(nodeActionForState\(state\), \$event\)"/)
assert.doesNotMatch(source, /class="workflow-node-action-trigger"/)
assert.doesNotMatch(source, /nodeActionTriggerBounds/)
assert.match(source, /event\.currentTarget\.getBoundingClientRect\(\)/)
assert.match(source, /workflowCanvasElement\.value\.getBoundingClientRect\(\)/)
assert.match(
  source,
  /class="workflow-node-action-badge"[\s\S]{0,650}@keydown\.esc\.stop\.prevent="closeNodeActionMenu"/
)
assert.match(source, /class="workflow-node-action-menu"/)
assert.match(source, /v-for="action in activeNodeActionMenu\.actions"/)
assert.match(source, /@click="selectNodeAction\(action\)"/)
assert.doesNotMatch(source, /v-for="action in nodeActionViews"/)
assert.match(source, /class="workflow-edge-endpoint"/)
assert.match(source, /class="workflow-edge-segment-hit"/)
assert.match(source, /startEndpointDrag/)
assert.match(source, /startSegmentDrag/)
assert.match(source, /cancelRouteDrag/)
assert.match(source, /@reset-diagram-route="resetSelectedDiagramRoute"/)
assert.ok(
  source.indexOf('</svg>') < source.indexOf('class="workflow-node-action-menu"'),
  'the floating action menu must render outside the SVG'
)
assert.doesNotMatch(source, /<aside class="workflow-config-panel">/)
assert.doesNotMatch(source, /workflow-details-drawer/)
assert.match(source, /<WorkflowAdvancedConfigDrawer/)
assert.match(source, /:state="drawerState"/)
assert.match(source, /:transitions="transitions"/)
assert.doesNotMatch(source, /\b(?:applyPanDelta|clampViewport|fitViewportToNodes)\([\s\S]{0,180}\bminimumCanvas\b/)
assert.match(source, /applyPanDelta\([\s\S]{0,180}canvasSize\.value/)
assert.match(
  source,
  /fitViewportToNodes\(states\.value, canvasSize\.value, viewportSize, fullTransitionViews\.value\)/
)
assert.match(source, /clampViewport\(\{ x: 0, y: 0 \}, canvasSize\.value, viewportSize\)/)

const canvasSizeWatchStart = source.indexOf('watch(canvasSize')
const configWatchStart = source.indexOf('watch(() => props.configId')
assert.ok(canvasSizeWatchStart >= 0, 'canvas size changes must clamp the current viewport')
assert.ok(configWatchStart > canvasSizeWatchStart, 'canvas size watcher must be defined before config loading watcher')
const canvasSizeWatch = source.slice(canvasSizeWatchStart, configWatchStart)
assert.match(canvasSizeWatch, /if \(dragging\.state \|\| suppressCanvasClamp\.value\) return[\s\S]*clampCurrentViewport\(nextCanvas\)/)
assert.match(canvasSizeWatch, /\{ flush: 'sync' \}/)
assert.doesNotMatch(canvasSizeWatch, /saveGraph|saveWorkflowDefinitionGraph|fetchWorkflowDefinitionGraph|applyWorkflowDefinitionTemplate/)

const clampCurrentViewportBody = functionBody('clampCurrentViewport', 'stopDrag')
assert.match(source, /function clampCurrentViewport\(nextCanvas = canvasSize\.value\)/)
assert.match(
  clampCurrentViewportBody,
  /const next = clampViewport\(\{ x: viewportOffset\.x, y: viewportOffset\.y \}, nextCanvas, viewportSize\)/
)
assert.match(clampCurrentViewportBody, /viewportOffset\.x = next\.x[\s\S]*viewportOffset\.y = next\.y/)

const stopDragBody = functionBody('stopDrag', 'startViewportDrag')
assert.match(stopDragBody, /suppressCanvasClamp\.value = true[\s\S]*dragging\.state = null/)
assert.match(stopDragBody, /const draggedStateId = dragging\.state\.id/)
assert.match(stopDragBody, /const finalState = dragFrame\.value\?\.states\.find/)
assert.match(stopDragBody, /dragging\.state\.x = finalState\.x[\s\S]*dragging\.state\.y = finalState\.y/)
assert.match(stopDragBody, /transitions\.value = applyGeneratedRoutesFromViews\(/)
assert.match(stopDragBody, /dragFrame\.value = null/)
assert.match(stopDragBody, /if \(dragging\.moved\)[\s\S]*suppressedStateClickId\.value = draggedStateId/)
assert.match(stopDragBody, /setTimeout\([\s\S]*suppressedStateClickId\.value = null[\s\S]*, 0\)/)
assert.doesNotMatch(stopDragBody, /clampCurrentViewport\(\)/)

const startDragBody = functionBody('startDrag', 'onDrag')
assert.match(startDragBody, /closeNodeActionMenu\(\)/)
assert.match(startDragBody, /dragging\.state = stateById\(state\.id\)/)
assert.match(startDragBody, /dragging\.moved = false/)
assert.doesNotMatch(startDragBody, /edgeViews|canvasEdges/)

const startEndpointDragBody = functionBody('startEndpointDrag', 'startSegmentDrag')
const startSegmentDragBody = functionBody('startSegmentDrag', 'beginRouteDrag')
assert.doesNotMatch(startEndpointDragBody, /onRouteDrag\(/)
assert.doesNotMatch(startSegmentDragBody, /onRouteDrag\(/)

const beginRouteDragBody = functionBody('beginRouteDrag', 'onRouteDrag')
assert.match(beginRouteDragBody, /if \(!isManualDiagramRoute\(transition\.diagram_config\)\)/)
assert.match(beginRouteDragBody, /createManualDiagramConfig\(edge, from, to\)/)

const startViewportDragBody = functionBody('startViewportDrag', 'onViewportDrag')
assert.match(startViewportDragBody, /closeNodeActionMenu\(\)/)

const onDragBody = functionBody('onDrag', 'clampCurrentViewport')
assert.match(source, /const NODE_DRAG_THRESHOLD = 4/)
assert.match(onDragBody, /const deltaX = event\.clientX - dragging\.startX/)
assert.match(onDragBody, /const deltaY = event\.clientY - dragging\.startY/)
assert.match(onDragBody, /deltaX \* deltaX \+ deltaY \* deltaY > NODE_DRAG_THRESHOLD \* NODE_DRAG_THRESHOLD/)
assert.match(onDragBody, /if \(!dragging\.moved\) return/)
assert.match(onDragBody, /canvasSize\.value\.right - 140/)
assert.match(onDragBody, /canvasSize\.value\.bottom - 70/)
assert.match(onDragBody, /requestAnimationFrame/)
assert.doesNotMatch(onDragBody, /canvasSize\.value\.(?:width|height)/)

const flushNodeDragBody = functionBody('flushNodeDrag', 'clampCurrentViewport')
assert.match(flushNodeDragBody, /dragFrame\.value = createWorkflowDragFrame\(/)
assert.doesNotMatch(flushNodeDragBody, /dragging\.state\.(?:x|y)\s*=/)

assert.match(
  source,
  /<el-button size="small" @click="addState">新增状态<\/el-button>\s*<el-button size="small" :loading="loading" @click="organizeLayout">整理布局<\/el-button>\s*<el-button size="small" @click="fitToContent">适应视图<\/el-button>/
)

const organizeLayoutBody = functionBody('organizeLayout', 'applyGraph')
assert.match(organizeLayoutBody, /const result = await requestWorkflowOrganization\(\{/)
assert.match(organizeLayoutBody, /states: states\.value/)
assert.match(organizeLayoutBody, /transitions: transitions\.value/)
assert.match(organizeLayoutBody, /initialStateId: initialStateId\.value/)
assert.match(
  organizeLayoutBody,
  /confirm: \(\) => ElMessageBox\.confirm\('整理布局将重新排列全部节点并清除手工布线，确认继续？', '整理布局', \{ type: 'warning' \}\)/
)
assert.match(organizeLayoutBody, /notifyEmpty: \(\) => ElMessage\.info\('当前没有可整理的状态节点'\)/)
assert.match(organizeLayoutBody, /if \(!result\.organized\) return/)
assert.match(organizeLayoutBody, /states\.value = result\.states/)
assert.match(organizeLayoutBody, /transitions\.value = result\.transitions/)
assert.doesNotMatch(organizeLayoutBody, /transition\.diagram_config = null/)
assert.match(organizeLayoutBody, /loading\.value = true[\s\S]*finally[\s\S]*loading\.value = false/)
assert.match(organizeLayoutBody, /ElMessage\.error\('整理布局失败，当前流程图未更改'\)/)
assert.doesNotMatch(
  organizeLayoutBody,
  /\bsaveGraph\s*\(|\bsaveWorkflowDefinitionGraph\s*\(|\bapplyWorkflowDefinitionTemplate\s*\(|\bfetchWorkflowDefinitionGraph\s*\(/
)

const applyGraphBody = functionBody('applyGraph', 'applyTemplate')
assert.match(source, /function applyGraph\(graph\)/)
assert.match(applyGraphBody, /stopRouteDrag\(\)/)
assert.match(applyGraphBody, /closeNodeActionMenu\(\)/)
assert.doesNotMatch(applyGraphBody, /organize|layoutWorkflow/)
assert.match(applyGraphBody, /fitToContent\(\)/)
assert.doesNotMatch(applyGraphBody, /captureSavedGraphSnapshot/)

const clearSelectionBody = functionBody('clearSelection', 'removeSelectedState')
assert.match(clearSelectionBody, /closeNodeActionMenu\(\)/)

const handleStateClickBody = functionBody('handleStateClick', 'selectState')
assert.match(handleStateClickBody, /if \(suppressedStateClickId\.value === state\.id\)/)
assert.match(handleStateClickBody, /suppressedStateClickId\.value = null[\s\S]*return/)
assert.match(handleStateClickBody, /selectState\(state\)/)

const selectStateBody = functionBody('selectState', 'selectTransition')
assert.match(selectStateBody, /closeNodeActionMenu\(\)/)

const selectTransitionBody = functionBody('selectTransition', 'clearSelection')
assert.match(selectTransitionBody, /closeNodeActionMenu\(\)/)

const loadDefinitionBody = functionBody('loadDefinition', 'organizeLayout')
assert.match(loadDefinitionBody, /applyGraph\(graph\.data\)/)
assert.match(loadDefinitionBody, /applyGraph\(graph\.data\)[\s\S]*captureSavedGraphSnapshot\(\)/)
assert.doesNotMatch(loadDefinitionBody, /applyGraph\(graph\.data, \{ organize: true \}\)/)

const applyTemplateBody = functionBody('applyTemplate', 'changeObjectType')
assert.match(applyTemplateBody, /confirmDiscardWorkflowChanges\(\{[\s\S]*force: true/)
assert.equal((applyTemplateBody.match(/ElMessageBox\.confirm/g) || []).length, 0)
assert.match(applyTemplateBody, /organized = await layoutWorkflowWithElk\(/)
assert.match(applyTemplateBody, /applyGraph\(\{[\s\S]*states: organized\.states[\s\S]*transitions: organized\.transitions[\s\S]*\}\)/)
assert.doesNotMatch(applyTemplateBody, /applyGraph\(graph\.data/)
assert.match(applyTemplateBody, /ElMessage\.error\('模板布局失败，当前流程图未更改'\)/)

const saveGraphBody = functionBody('saveGraph', 'addState')
assert.match(saveGraphBody, /applyGraph\(graph\.data\)/)
assert.match(saveGraphBody, /applyGraph\(graph\.data\)[\s\S]*captureSavedGraphSnapshot\(\)/)
assert.doesNotMatch(saveGraphBody, /applyGraph\(graph\.data, \{ organize: true \}\)/)

assert.match(source, /const savedGraphSnapshot = ref\(''\)/)
assert.match(source, /const currentGraphSnapshot = computed\(\(\) => workflowGraphSnapshot\(\{/)
assert.match(source, /const hasUnsavedGraphChanges = computed\(/)
assert.match(source, /onBeforeRouteLeave\(async \(\) => confirmDiscardWorkflowChanges\(\)\)/)

const confirmDiscardBody = functionBody('confirmDiscardWorkflowChanges', 'onBeforeUnload')
const hasPendingBody = functionBody('hasPendingWorkflowChanges', 'confirmDiscardWorkflowChanges')
assert.match(hasPendingBody, /hasUnsavedGraphChanges\.value/)
assert.match(hasPendingBody, /advancedDrawer\.value\?\.hasPendingChanges\?\.\(\)/)
assert.match(confirmDiscardBody, /hasPendingWorkflowChanges\(\)/)
assert.match(confirmDiscardBody, /ElMessageBox\.confirm/)

const beforeUnloadBody = functionBody('onBeforeUnload', 'eventToCanvasPoint')
assert.match(beforeUnloadBody, /hasPendingWorkflowChanges\(\)/)

console.log('workflow designer auto layout source contract passed')
