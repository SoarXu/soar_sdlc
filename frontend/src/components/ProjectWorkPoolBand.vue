<template>
  <section class="work-pool-band" :class="{ 'has-work': totalCount > 0 }">
    <div class="work-pool-heading">
      <span class="work-pool-kicker">待规划工作池</span>
      <strong>待规划 {{ totalCount }} 项</strong>
    </div>
    <div class="work-pool-counts" aria-label="待规划事项统计">
      <button type="button" @click="emit('view', 'requirement')">
        <span>需求</span><b>{{ summary?.requirement_count || 0 }}</b>
      </button>
      <button type="button" @click="emit('view', 'task')">
        <span>任务</span><b>{{ summary?.task_count || 0 }}</b>
      </button>
      <button type="button" @click="emit('view', 'bug')">
        <span>Bug</span><b>{{ summary?.bug_count || 0 }}</b>
      </button>
    </div>
    <div class="work-pool-actions">
      <el-button :icon="View" @click="emit('view', 'requirement')">查看事项</el-button>
      <el-button v-if="canPlan && totalCount > 0" type="primary" :icon="FolderAdd" @click="emit('plan')">
        纳入迭代
      </el-button>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { FolderAdd, View } from '@element-plus/icons-vue'

const props = defineProps({
  summary: { type: Object, default: null },
  canPlan: { type: Boolean, default: false }
})
const emit = defineEmits(['view', 'plan'])
const totalCount = computed(() => props.summary?.total_count || 0)
</script>

<style scoped>
.work-pool-band {
  display: grid;
  grid-template-columns: minmax(180px, 1fr) minmax(280px, auto) auto;
  align-items: center;
  gap: 24px;
  width: 100%;
  min-height: 88px;
  margin-bottom: 18px;
  padding: 16px 18px;
  background: #f7faf8;
  border: 1px solid #d8e4dd;
  border-left: 4px solid #4f7a62;
  border-radius: 6px;
}

.work-pool-band.has-work {
  background: #fffaf0;
  border-color: #ead7a8;
  border-left-color: #c87920;
}

.work-pool-heading {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.work-pool-heading strong {
  color: #1f2937;
  font-size: 22px;
  line-height: 1.25;
}

.work-pool-kicker {
  color: #6b7280;
  font-size: 13px;
}

.work-pool-counts {
  display: grid;
  grid-template-columns: repeat(3, minmax(76px, 1fr));
  gap: 8px;
}

.work-pool-counts button {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  min-height: 42px;
  padding: 8px 10px;
  color: #4b5563;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid rgba(148, 163, 184, 0.42);
  border-radius: 4px;
  cursor: pointer;
}

.work-pool-counts button:hover {
  color: var(--el-color-primary);
  border-color: var(--el-color-primary-light-5);
}

.work-pool-counts b {
  color: #111827;
  font-size: 18px;
}

.work-pool-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

@media (max-width: 900px) {
  .work-pool-band {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .work-pool-actions {
    justify-content: flex-start;
  }
}
</style>
