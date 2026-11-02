<template>
  <el-select
    :model-value="modelValue"
    filterable
    remote
    clearable
    :remote-method="search"
    :loading="loading"
    placeholder="请选择提出人"
    @update:model-value="$emit('update:modelValue', $event)"
    @visible-change="onVisibleChange"
  >
    <el-option
      v-if="modelValue && !options.some((item) => item.full_name === modelValue)"
      :label="modelValue"
      :value="modelValue"
      disabled
    />
    <el-option v-for="user in options" :key="user.username" :label="user.full_name" :value="user.full_name">
      <span>{{ user.full_name }}</span>
      <small class="directory-account">{{ user.username }}{{ user.employee_no ? ` · ${user.employee_no}` : '' }}</small>
    </el-option>
    <el-option v-if="errorMessage" :label="errorMessage" value="__directory_error__" disabled />
  </el-select>
</template>

<script setup>
import { onBeforeUnmount, ref } from 'vue'

import { fetchLdapProposers } from '../../api/directory'
import { actionErrorMessage } from '../../utils/permissions'

defineProps({ modelValue: { type: String, default: '' } })
defineEmits(['update:modelValue'])

const options = ref([])
const loading = ref(false)
const errorMessage = ref('')
let timer
let requestId = 0

async function load(query) {
  const currentRequest = ++requestId
  loading.value = true
  errorMessage.value = ''
  try {
    const { data } = await fetchLdapProposers(query.trim())
    if (currentRequest === requestId) options.value = data || []
  } catch (error) {
    if (currentRequest === requestId) {
      options.value = []
      errorMessage.value = actionErrorMessage(error) || 'AD 人员查询失败'
    }
  } finally {
    if (currentRequest === requestId) loading.value = false
  }
}

function search(query) {
  clearTimeout(timer)
  timer = setTimeout(() => load(query), 250)
}

function onVisibleChange(visible) {
  if (visible) load('')
  else clearTimeout(timer)
}

onBeforeUnmount(() => {
  clearTimeout(timer)
  requestId += 1
})
</script>

<style scoped>
.directory-account {
  float: right;
  color: var(--el-text-color-secondary);
  margin-left: 12px;
}
</style>
