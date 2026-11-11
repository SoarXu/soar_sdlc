<template>
  <el-select :model-value="modelValue" filterable remote clearable :remote-method="search" :loading="loading" placeholder="搜索 AD 姓名、账号或工号" @visible-change="visible => visible && load('')" @update:model-value="$emit('update:modelValue', $event)">
    <el-option v-for="person in people" :key="person.external_id" :value="person.external_id" :label="person.full_name || person.username">
      {{ person.full_name || person.username }}
      <small>{{ person.username }} · {{ person.department || '未填写部门' }}{{ person.employee_no ? ` · ${person.employee_no}` : '' }}</small>
    </el-option>
    <el-option v-if="errorMessage" value="__error__" :label="errorMessage" disabled />
  </el-select>
</template>

<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { fetchRequirementImportProposers } from '../api/requirements'
import { actionErrorMessage } from '../utils/permissions'

const props = defineProps({ modelValue: { type: String, default: '' }, candidates: { type: Array, default: () => [] }, selected: { type: Object, default: null } })
defineEmits(['update:modelValue'])
const options = ref([])
const loading = ref(false)
const errorMessage = ref('')
const people = computed(() => [...new Map([...props.candidates, ...options.value, ...(props.selected ? [props.selected] : [])].map(p => [p.external_id, p])).values()])
let timer, requestId = 0
async function load(query) {
  const id = ++requestId
  loading.value = true
  errorMessage.value = ''
  try {
    const { data } = await fetchRequirementImportProposers(query)
    if (id === requestId) options.value = data || []
  } catch (error) {
    if (id === requestId) errorMessage.value = actionErrorMessage(error) || 'AD 人员查询失败'
  } finally {
    if (id === requestId) loading.value = false
  }
}
function search(query) { clearTimeout(timer); timer = setTimeout(() => load(query.trim()), 250) }
onBeforeUnmount(() => { clearTimeout(timer); requestId++ })
</script>

<style scoped>
small { margin-left: 12px; color: var(--el-text-color-secondary); }
</style>
