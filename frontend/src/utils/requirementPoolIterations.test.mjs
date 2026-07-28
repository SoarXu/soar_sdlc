import assert from 'node:assert/strict'
import {
  deliveryIterations,
  requirementIterationLabel,
  requirementIterationOptions,
  requirementPoolForProject
} from './requirementPoolIterations.js'

function run(name, fn) {
  try {
    fn()
    console.log(`ok - ${name}`)
  } catch (error) {
    console.error(`not ok - ${name}`)
    throw error
  }
}

const projects = [
  { id: 1, name: '父项目' },
  { id: 2, name: '子项目', parent_id: 1 },
  { id: 3, name: '同级项目', parent_id: 1 }
]

const childProject = {
  ...projects[1],
  requirement_pool_iteration_id: 11
}

const items = [
  { id: 10, name: '父项目需求池', is_requirement_pool: true, project_ids: [1] },
  { id: 11, name: '需求池名称', is_requirement_pool: true, project_ids: [2] },
  { id: 12, name: '父项目迭代', is_requirement_pool: false, project_ids: [1] },
  { id: 13, name: '子项目终态迭代', is_requirement_pool: false, state_category: 'terminal', project_ids: [2] },
  { id: 14, name: '同级项目迭代', is_requirement_pool: false, project_ids: [3] },
  { id: 15, name: '同级项目需求池', is_requirement_pool: true, project_ids: [3] }
]

run('returns only delivery iterations', () => {
  assert.deepEqual(deliveryIterations(items).map((item) => item.id), [12, 13, 14])
})

run('finds a requirement pool only through the canonical project reference and pool flag', () => {
  assert.equal(requirementPoolForProject(childProject, items).id, 11)
  assert.equal(
    requirementPoolForProject({ ...childProject, requirement_pool_iteration_id: 12 }, items),
    null
  )
})

run('does not select an arbitrary flagged pool when the project reference is missing', () => {
  assert.equal(requirementPoolForProject({ id: 2 }, items), null)
  assert.equal(
    requirementPoolForProject({ ...childProject, requirement_pool_iteration_id: 999 }, items),
    null
  )
})

run('puts the canonical pool first then delivery iterations scoped to the project or its ancestors', () => {
  assert.deepEqual(
    requirementIterationOptions(childProject, projects, items).map((item) => item.id),
    [11, 12, 13]
  )
})

run('keeps terminal delivery iterations available for requirement planning', () => {
  const options = requirementIterationOptions(childProject, projects, items)

  assert.equal(options.some((item) => item.id === 13), true)
})

run('adds the planning suffix only to requirement pool display labels', () => {
  assert.equal(requirementIterationLabel(items[1]), '需求池名称（未排期）')
  assert.equal(requirementIterationLabel(items[2]), '父项目迭代')
  assert.equal(items[1].name, '需求池名称')
})
