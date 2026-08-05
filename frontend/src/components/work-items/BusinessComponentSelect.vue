<template>
  <el-select
    :model-value="modelValue"
    clearable
    filterable
    :loading="loading"
    placeholder="请选择业务组件"
    @update:model-value="$emit('update:modelValue', $event || null)"
  >
    <el-option v-for="component in enabledComponents" :key="component.id" :label="component.name" :value="component.id" />
  </el-select>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { fetchBusinessComponents } from '../../api/businessComponents'

const props = defineProps({
  modelValue: { type: Number, default: null },
  projectId: { type: Number, default: null }
})

const emit = defineEmits(['update:modelValue'])
const loading = ref(false)
const components = ref([])
const enabledComponents = computed(() => components.value.filter((component) => component.enabled))

watch(() => props.projectId, async (projectId) => {
  if (!projectId) {
    components.value = []
    emit('update:modelValue', null)
    return
  }
  loading.value = true
  try {
    const { data } = await fetchBusinessComponents(projectId)
    components.value = data
    if (props.modelValue && !enabledComponents.value.some((component) => component.id === props.modelValue)) {
      emit('update:modelValue', null)
    }
  } finally {
    loading.value = false
  }
}, { immediate: true })
</script>
