<template>
  <div class="gantt-view">
    <BaseChart :option="option" height="520px" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import BaseChart from '@/components/common/BaseChart.vue'
import { buildGanttOption, type GanttItem } from '@/utils/gantt'

const props = defineProps<{ items: GanttItem[] }>()
const option = computed(() => buildGanttOption(props.items, Date.now()))
</script>

<style scoped>
.gantt-view {
  background: var(--color-bg-card);
  border-radius: 8px;
  padding: 12px;
}
</style>
