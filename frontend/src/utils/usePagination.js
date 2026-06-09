import { computed, ref, watch } from 'vue'

export function usePagination(source, initialPageSize = 10) {
  const page = ref(1)
  const pageSize = ref(initialPageSize)
  const pageSizes = [10, 20, 50, 100]
  const total = computed(() => source.value.length)
  const pagedItems = computed(() => {
    const start = (page.value - 1) * pageSize.value
    return source.value.slice(start, start + pageSize.value)
  })

  watch([total, pageSize], () => {
    const maxPage = Math.max(1, Math.ceil(total.value / pageSize.value))
    if (page.value > maxPage) page.value = maxPage
  })

  return { page, pageSize, pageSizes, total, pagedItems }
}
