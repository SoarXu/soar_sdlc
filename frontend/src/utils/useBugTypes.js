import { computed, onMounted, ref } from 'vue'

import { fetchBugTypes } from '../api/bugTypes'
import { toBugTypeOptions } from './bugTypeOptions'


export function useBugTypes() {
  const bugTypes = ref([])
  const bugTypeOptions = computed(() => toBugTypeOptions(bugTypes.value))

  async function loadBugTypes() {
    const { data } = await fetchBugTypes()
    bugTypes.value = data
  }

  function bugTypeLabel(value) {
    return bugTypeOptions.value.find((item) => item.value === value)?.label || value || '-'
  }

  onMounted(loadBugTypes)

  return { bugTypes, bugTypeOptions, bugTypeLabel, loadBugTypes }
}
