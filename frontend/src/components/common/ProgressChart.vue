<template>
  <div class="progress-chart">
    <div class="progress-label">{{ label }}</div>
    <el-progress :percentage="percentage" :color="color" :stroke-width="strokeWidth" />
    <div class="progress-text">{{ text }}</div>
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    label?: string
    percentage: number
    color?: string
    strokeWidth?: number
    text?: string
  }>(),
  { label: '', color: '#40916c', strokeWidth: 12, text: '' }
)
</script>

<style scoped>
.progress-chart {
  margin: 10px 0;
}
.progress-label {
  font-size: 14px;
  margin-bottom: 4px;
  color: var(--color-text-primary);
}
.progress-text {
  font-size: 12px;
  color: var(--color-text-placeholder);
  margin-top: 2px;
}
</style>
