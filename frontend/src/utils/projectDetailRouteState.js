const DEFAULT_PAGE = 1
const DEFAULT_PAGE_SIZE = 10
const DEFAULT_TEST_TAB = 'cases'
const LIST_KEYS = ['requirements', 'tasks', 'testCases', 'testRuns', 'bugs']

function firstValue(value) {
  return Array.isArray(value) ? value[0] : value
}

function positiveInteger(value, fallback) {
  const candidate = firstValue(value)
  const parsed = Number(candidate)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback
}

function positiveId(value) {
  const candidate = firstValue(value)
  if (candidate == null || candidate === '') return null
  const parsed = Number(candidate)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null
}

function parseListState(query, key) {
  const keywordValue = firstValue(query[`${key}_keyword`])
  return {
    keyword: keywordValue == null ? '' : String(keywordValue),
    iteration_id: positiveId(query[`${key}_iteration_id`]),
    unfinished_work_items: ['1', 'true', 1, true].includes(firstValue(query[`${key}_unfinished_work_items`])),
    page: positiveInteger(query[`${key}_page`], DEFAULT_PAGE),
    pageSize: positiveInteger(query[`${key}_page_size`], DEFAULT_PAGE_SIZE)
  }
}

export function parseProjectDetailRouteState(query = {}) {
  const testTab = firstValue(query.test_tab)
  return {
    testTab: testTab === 'runs' ? 'runs' : DEFAULT_TEST_TAB,
    ...Object.fromEntries(LIST_KEYS.map((key) => [key, parseListState(query, key)]))
  }
}

export function serializeProjectDetailRouteState(state = {}) {
  const query = {}
  if (state.testTab === 'runs') query.test_tab = 'runs'

  for (const key of LIST_KEYS) {
    const list = state[key] || {}
    const keyword = list.keyword == null ? '' : String(list.keyword)
    const iterationId = positiveId(list.iteration_id)
    const page = positiveInteger(list.page, DEFAULT_PAGE)
    const pageSize = positiveInteger(list.pageSize, DEFAULT_PAGE_SIZE)

    if (keyword) query[`${key}_keyword`] = keyword
    if (iterationId != null) query[`${key}_iteration_id`] = String(iterationId)
    if (list.unfinished_work_items) query[`${key}_unfinished_work_items`] = '1'
    if (page !== DEFAULT_PAGE) query[`${key}_page`] = String(page)
    if (pageSize !== DEFAULT_PAGE_SIZE) query[`${key}_page_size`] = String(pageSize)
  }

  return query
}

export function projectDetailRouteQuery(state) {
  return serializeProjectDetailRouteState(state)
}

export { DEFAULT_PAGE, DEFAULT_PAGE_SIZE, LIST_KEYS }
