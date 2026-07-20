import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'


const sources = [
  'frontend/src/views/ProgramsView.vue',
  'frontend/src/views/ProjectsView.vue',
  'frontend/src/views/ProjectDetailView.vue',
  'frontend/src/views/IterationsView.vue',
  'frontend/src/views/IterationDetailView.vue',
  'frontend/src/utils/bugIterations.js'
].map((path) => [path, readFileSync(path, 'utf8')])

const forbidden = [
  /projectStatusLabel\([^)]*\.status\)/,
  /iterationStatusLabel\([^)]*\.status\)/,
  /project\.value\.status\s*===/,
  /iteration\.status\)/,
  /TERMINAL_ITERATION_STATUSES/
]
const rowStatusGate = /row\.status\s*===\s*['"](?:planning|active|paused|closed|completed|canceled)/

for (const [path, source] of sources) {
  for (const pattern of forbidden) {
    assert.equal(pattern.test(source), false, `${path} still depends on ${pattern}`)
  }
  if (!path.endsWith('ProgramsView.vue')) {
    assert.equal(rowStatusGate.test(source), false, `${path} still depends on ${rowStatusGate}`)
  }
}

const programsSource = sources.find(([path]) => path.endsWith('ProgramsView.vue'))[1]
const projectsSource = sources.find(([path]) => path.endsWith('ProjectsView.vue'))[1]
const programActionBranch = programsSource.match(/<template v-if="row\.nodeType === 'program'">([\s\S]*?)<\/template>\s*<template v-else>/)?.[1] || ''
const projectActionBranch = programsSource.match(/<template v-else>([\s\S]*?)<\/template>/)?.[1] || ''
assert.match(programActionBranch, /row\.status/, 'ProgramsView.vue program actions may continue using Program.status')
assert.ok(projectActionBranch, 'ProgramsView.vue project action branch must be present')
assert.doesNotMatch(projectActionBranch, /row\.status/, 'ProgramsView.vue project actions must not read row.status')
assert.doesNotMatch(projectActionBranch, /['"](?:planning|active|paused|closed)['"]/, 'ProgramsView.vue project actions must not use string status gates')
assert.match(programsSource, /fetchWorkflowTransitionsBatch/, 'ProgramsView.vue must batch-load project transitions')
assert.doesNotMatch(programsSource, /action_key/, 'ProgramsView.vue must not depend on internal transition action keys')
assert.match(projectActionBranch, /WorkflowActionButtons/, 'ProgramsView.vue project actions must use runtime transition buttons')
assert.match(programsSource, /row\.status_name/, 'ProgramsView.vue project status display must use status_name')
assert.match(programsSource, /programOperationWidth[\s\S]*flatProjects\.value/, 'ProgramsView.vue operation width must include nested project rows')
assert.match(projectsSource, /projectOperationWidth[\s\S]*projects\.value/, 'ProjectsView.vue operation width must include child project rows')

const statusDateRequired = programsSource.match(/const statusDateRequired = computed\(\(\) =>[^\n]+/)?.[0] || ''
assert.ok(statusDateRequired, 'ProgramsView.vue status date gate must be present')
assert.doesNotMatch(statusDateRequired, /statusTarget\.value\?\.status/, 'ProgramsView.vue project date gate must not read project.status')
const startDateRequired = programsSource.match(/function startDateRequired\(\) \{([\s\S]*?)\n\}/)?.[1] || ''
const projectStartDateGate = startDateRequired.match(/return !statusTarget\.value\?\.actual_start_date/)?.[0] || ''
assert.match(startDateRequired, /statusTargetType\.value === 'program'/, 'ProgramsView.vue must scope legacy status checks to programs')
assert.match(projectStartDateGate, /actual_start_date/, 'ProgramsView.vue project start date gate must use project date identity')
assert.doesNotMatch(projectStartDateGate, /\.status/, 'ProgramsView.vue project start date gate must not read project.status')

const projectDetailSource = sources.find(([path]) => path.endsWith('ProjectDetailView.vue'))[1]
assert.doesNotMatch(projectDetailSource, /\[['"]completed['"],\s*['"]canceled['"]\]\.includes\(item\.status\)/, 'ProjectDetailView.vue iteration filters must use state_category')

for (const [path, gateName, guardedActions] of [
  ['frontend/src/views/RequirementsView.vue', 'isRequirementProjectClosed', ['canGenerateTask', 'canDeleteRequirement']],
  ['frontend/src/views/TasksView.vue', 'isTaskProjectClosed', ['canDeleteTaskRow']]
]) {
  const source = readFileSync(path, 'utf8')
  const gate = source.match(new RegExp(`function ${gateName}\\(row\\) \\{([^}]*)\\}`))?.[1] || ''
  assert.ok(gate, `${path} terminal-project gate must be present`)
  assert.match(gate, /\.state_category\s*===\s*['"]terminal['"]/, `${path} terminal-project gate must use state_category`)
  assert.doesNotMatch(gate, /\.status\b/, `${path} terminal-project gate must not read removed project.status`)
  for (const actionName of guardedActions) {
    const action = source.match(new RegExp(`function ${actionName}\\([^)]*\\) \\{([\\s\\S]*?)\\n\\}`))?.[1] || ''
    assert.match(action, new RegExp(`${gateName}\\(row\\)`), `${path} ${actionName} must retain the terminal-project guard`)
  }
  assert.match(source, /<WorkflowActionButtons\b/, `${path} edit commands must remain workflow-action driven`)
}

for (const [path, source] of sources.filter(([path]) => /(?:Programs|Projects)View\.vue$/.test(path))) {
  const loadData = source.match(/async function loadData\(\) \{([\s\S]*?)^\}/m)?.[1] || ''
  assert.ok(loadData, path + ' loadData must be present')
  assert.doesNotMatch(loadData, /fetchWorkflowTransitionsBatch/, path + ' base list load must not own transition failures')
  assert.match(source, /async function loadProjectWorkflowTransitions\(\)/, path + ' must load project actions separately')
  assert.match(source, /ElMessage\.error\('项目动作加载失败'\)/, path + ' must distinguish project action loading errors')
  assert.match(source, /workflowActionColumnWidth/, path + ' must calculate the operation column from runtime actions')
  assert.match(source, /:width="[^\"]*[Oo]perationWidth"/, path + ' must bind the calculated operation column width')
  assert.doesNotMatch(source, /<el-table-column label="操作" width="(?:330|440)"/, path + ' must not retain a fixed operation column width')
}

console.log('project and iteration state identity source contract passed')
