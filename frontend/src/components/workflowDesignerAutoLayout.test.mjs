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

assert.match(source, /import \{ layoutWorkflowNodes \} from '\.\.\/utils\/workflowAutoLayout'/)
assert.match(source, /import \{ buildWorkflowEdgeViews \} from '\.\.\/utils\/workflowEdgePath'/)
assert.match(source, /import \{ requestWorkflowOrganization \} from '\.\.\/utils\/workflowLayoutInteraction'/)
assert.match(source, /workflowCanvasSize/)
assert.doesNotMatch(source, /\bbuildWorkflowEdgeView\b/)
assert.match(
  source,
  /const transitionViews = computed\(\(\) => buildWorkflowEdgeViews\(states\.value, transitions\.value, transitionKey\)\)/
)
assert.match(source, /const minimumCanvas = \{ width: 2400, height: 1400 \}/)
assert.match(source, /const canvasSize = computed\(\(\) => workflowCanvasSize\(states\.value, minimumCanvas\)\)/)
assert.doesNotMatch(source, /\b(?:applyPanDelta|clampViewport|fitViewportToNodes)\([\s\S]{0,180}\bminimumCanvas\b/)
assert.match(source, /applyPanDelta\([\s\S]{0,180}canvasSize\.value/)
assert.match(source, /fitViewportToNodes\(states\.value, canvasSize\.value, viewportSize\)/)
assert.match(source, /clampViewport\(\{ x: 0, y: 0 \}, canvasSize\.value, viewportSize\)/)

const canvasSizeWatchStart = source.indexOf('watch(canvasSize')
const configWatchStart = source.indexOf('watch(() => props.configId')
assert.ok(canvasSizeWatchStart >= 0, 'canvas size changes must clamp the current viewport')
assert.ok(configWatchStart > canvasSizeWatchStart, 'canvas size watcher must be defined before config loading watcher')
const canvasSizeWatch = source.slice(canvasSizeWatchStart, configWatchStart)
assert.match(canvasSizeWatch, /if \(dragging\.state\) return[\s\S]*clampCurrentViewport\(nextCanvas\)/)
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
assert.match(stopDragBody, /dragging\.state = null[\s\S]*clampCurrentViewport\(\)/)

assert.match(
  source,
  /<el-button size="small" @click="addTransition">新增流转<\/el-button>\s*<el-button size="small" @click="organizeLayout">整理布局<\/el-button>\s*<el-button size="small" @click="fitToContent">适应视图<\/el-button>/
)

const applyOrganizedLayoutBody = functionBody('applyOrganizedLayout', 'organizeLayout')
assert.match(
  applyOrganizedLayoutBody,
  /states\.value = layoutWorkflowNodes\(states\.value, transitions\.value, initialStateId\.value\)/
)

const organizeLayoutBody = functionBody('organizeLayout', 'applyGraph')
assert.match(organizeLayoutBody, /const result = await requestWorkflowOrganization\(\{/)
assert.match(organizeLayoutBody, /states: states\.value/)
assert.match(organizeLayoutBody, /transitions: transitions\.value/)
assert.match(organizeLayoutBody, /initialStateId: initialStateId\.value/)
assert.match(
  organizeLayoutBody,
  /confirm: \(\) => ElMessageBox\.confirm\('整理布局将重新排列全部节点，确认继续？', '整理布局', \{ type: 'warning' \}\)/
)
assert.match(organizeLayoutBody, /notifyEmpty: \(\) => ElMessage\.info\('当前没有可整理的状态节点'\)/)
assert.match(organizeLayoutBody, /if \(!result\.organized\) return/)
assert.match(organizeLayoutBody, /states\.value = result\.states/)
assert.match(organizeLayoutBody, /states\.value = result\.states[\s\S]*fitToContent\(\)/)
assert.doesNotMatch(
  organizeLayoutBody,
  /\bsaveGraph\s*\(|\bsaveWorkflowDefinitionGraph\s*\(|\bapplyWorkflowDefinitionTemplate\s*\(|\bfetchWorkflowDefinitionGraph\s*\(/
)

const applyGraphBody = functionBody('applyGraph', 'applyTemplate')
assert.match(source, /function applyGraph\(graph, \{ organize = false \} = \{\}\)/)
assert.match(applyGraphBody, /if \(organize\) applyOrganizedLayout\(\)/)
assert.match(applyGraphBody, /fitToContent\(\)/)

const loadDefinitionBody = functionBody('loadDefinition', 'applyOrganizedLayout')
assert.match(loadDefinitionBody, /applyGraph\(graph\.data\)/)
assert.doesNotMatch(loadDefinitionBody, /applyGraph\(graph\.data, \{ organize: true \}\)/)

const applyTemplateBody = functionBody('applyTemplate', 'changeObjectType')
assert.match(applyTemplateBody, /applyGraph\(graph\.data, \{ organize: true \}\)/)

const saveGraphBody = functionBody('saveGraph', 'addState')
assert.match(saveGraphBody, /applyGraph\(graph\.data\)/)
assert.doesNotMatch(saveGraphBody, /applyGraph\(graph\.data, \{ organize: true \}\)/)

console.log('workflow designer auto layout source contract passed')
