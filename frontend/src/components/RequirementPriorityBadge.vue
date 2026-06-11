<template>
  <span class="priority-badge" :class="`priority-badge--${normalized}`" :title="title" :aria-label="title">{{ normalized }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: {
    type: [String, Number],
    default: ''
  }
})

const legacyPriorityValues = { high: '1', medium: '3', low: '5' }
const normalized = computed(() => legacyPriorityValues[props.value] || String(props.value || '-'))
const title = computed(() => `需求优先级 ${normalized.value}，1 最高，5 最低`)
</script>
