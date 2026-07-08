import { labelById, userLabel } from './referenceLabels.js'

const USER_FIELDS = new Set(['owner_id', 'proposer_id', 'reporter_id', 'default_tester_id', 'test_owner_id', 'creator_id', 'updater_id'])
const PROJECT_FIELDS = new Set(['project_id', 'source_project_id', 'parent_id'])
const REQUIREMENT_FIELDS = new Set(['requirement_id'])
const TASK_FIELDS = new Set(['task_id'])
const TEST_CASE_FIELDS = new Set(['test_case_id'])
const TEST_RUN_FIELDS = new Set(['test_run_id'])
const ITERATION_FIELDS = new Set(['iteration_id'])
const PROGRAM_FIELDS = new Set(['program_id'])
const ASSIGNEE_RULE_CONFIG_FIELDS = new Set(['assignee_rule_config_id'])
const WORKFLOW_RULE_FIELDS = new Set(['workflow_config_id', 'workflow_rule_id'])

const FIELD_OPTION_CONTEXT = {
  status: 'statusOptions',
  lifecycle_phase: 'lifecyclePhaseOptions',
  priority: 'priorityOptions',
  severity: 'priorityOptions',
  requirement_type: 'requirementTypeOptions',
  case_type: 'caseTypeOptions',
  test_scope: 'testScopeOptions',
  last_execute_result: 'executionResultOptions',
  result: 'executionResultOptions',
  bug_type: 'bugTypeOptions',
  resolution: 'bugResolutionOptions',
  project_role: 'projectMemberRoleOptions'
}

function emptyValue(value) {
  return value === null || value === undefined || value === ''
}

export function formatAuditValue(field, value, context = {}) {
  if (emptyValue(value)) return '-'
  if (USER_FIELDS.has(field)) return userLabel(context.users || [], value)
  if (PROJECT_FIELDS.has(field)) return labelById(context.projects || [], value)
  if (PROGRAM_FIELDS.has(field)) return labelById(context.programs || [], value)
  if (ASSIGNEE_RULE_CONFIG_FIELDS.has(field)) return labelById(context.assigneeRuleConfigs || [], value)
  if (WORKFLOW_RULE_FIELDS.has(field)) return labelById(context.workflowRules || [], value)
  if (ITERATION_FIELDS.has(field)) return labelById(context.iterations || [], value)
  if (REQUIREMENT_FIELDS.has(field)) return labelById(context.requirements || [], value, 'title')
  if (TASK_FIELDS.has(field)) return labelById(context.tasks || [], value, 'title')
  if (TEST_CASE_FIELDS.has(field)) return labelById(context.testCases || [], value, 'title')
  if (TEST_RUN_FIELDS.has(field)) return labelById(context.testRuns || [], value, 'name')
  const optionContextKey = FIELD_OPTION_CONTEXT[field]
  if (optionContextKey && context[optionContextKey]) return optionLabel(context[optionContextKey], value)
  if (typeof value === 'boolean') return value ? '是' : '否'
  return value
}

function optionLabel(options, value) {
  if (Array.isArray(options)) {
    if (typeof options[0] === 'string') return options.includes(value) ? value : value || '-'
    return options.find((option) => option.value === value)?.label || value || '-'
  }
  return value || '-'
}
