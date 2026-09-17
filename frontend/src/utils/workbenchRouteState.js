const DEFAULT_PAGE = 1
const DEFAULT_PAGE_SIZE = 20

const MULTI_VALUE_FIELDS = [
  ['projectIds', 'project_ids'],
  ['iterationIds', 'iteration_ids'],
  ['types', 'object_types'],
  ['stateIds', 'state_ids'],
  ['priorities', 'priorities'],
  ['handlerIds', 'handler_ids']
]
const NUMERIC_MULTI_VALUE_KEYS = new Set(['projectIds', 'iterationIds', 'stateIds', 'handlerIds'])

function queryValues(value) {
  const values = Array.isArray(value) ? value : [value]
  return values
    .flatMap((item) => item == null ? [] : String(item).split(','))
    .map((item) => item.trim())
    .filter(Boolean)
}

function positiveInteger(value, fallback) {
  const candidate = Array.isArray(value) ? value[0] : value
  const parsed = Number(candidate)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback
}

export function parseWorkbenchRouteState(query = {}) {
  const state = {
    keyword: query.keyword == null
      ? ''
      : String(Array.isArray(query.keyword) ? query.keyword[0] ?? '' : query.keyword),
    page: positiveInteger(query.page, DEFAULT_PAGE),
    pageSize: positiveInteger(query.page_size, DEFAULT_PAGE_SIZE)
  }

  for (const [stateKey, queryKey] of MULTI_VALUE_FIELDS) {
    const values = queryValues(query[queryKey])
    state[stateKey] = NUMERIC_MULTI_VALUE_KEYS.has(stateKey)
      ? values.map(Number).filter((value) => Number.isInteger(value) && value > 0)
      : values
  }

  return state
}

export function serializeWorkbenchRouteState(state = {}) {
  const query = {}
  const keyword = state.keyword == null ? '' : String(state.keyword)
  const page = positiveInteger(state.page, DEFAULT_PAGE)
  const pageSize = positiveInteger(state.pageSize, DEFAULT_PAGE_SIZE)

  if (keyword) query.keyword = keyword

  for (const [stateKey, queryKey] of MULTI_VALUE_FIELDS) {
    const values = queryValues(state[stateKey])
    if (values.length) query[queryKey] = values.join(',')
  }

  if (page !== DEFAULT_PAGE) query.page = String(page)
  if (pageSize !== DEFAULT_PAGE_SIZE) query.page_size = String(pageSize)

  return query
}

export function workbenchRouteQuery(state) {
  return serializeWorkbenchRouteState(state)
}
