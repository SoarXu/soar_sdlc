<template>
  <el-button
    plain
    :type="watchState.watched ? 'primary' : 'default'"
    :loading="loading"
    class="watch-toggle-button"
    @click="toggleWatch"
  >
    {{ watchState.watched ? '已关注' : '关注' }}<span class="watch-toggle-count">{{ watchState.watcher_count || 0 }}</span>
  </el-button>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

import { fetchObjectWatch, unwatchObject, watchObject } from '../api/objectWatches'

const props = defineProps({
  objectType: { type: String, required: true },
  objectId: { type: Number, required: true }
})

const loading = ref(false)
const watchState = reactive({ watched: false, watcher_count: 0, watchers: [] })

async function loadState() {
  if (!props.objectType || !props.objectId) return
  loading.value = true
  try {
    const { data } = await fetchObjectWatch(props.objectType, props.objectId)
    Object.assign(watchState, data)
  } finally {
    loading.value = false
  }
}

async function toggleWatch() {
  loading.value = true
  try {
    if (watchState.watched) {
      await unwatchObject(props.objectType, props.objectId)
      ElMessage.success('已取消关注')
    } else {
      await watchObject(props.objectType, props.objectId)
      ElMessage.success('已关注')
    }
    await loadState()
  } finally {
    loading.value = false
  }
}

watch(() => [props.objectType, props.objectId], loadState)
onMounted(loadState)
</script>

<style scoped>
.watch-toggle-button {
  min-width: 92px;
}

.watch-toggle-count {
  margin-left: 6px;
  opacity: .72;
}
</style>
