<template>
  <div class="stats-card" :class="[`stats-card--${type}`]">
    <div class="stats-card__header">
      <span class="stats-card__title">{{ title }}</span>
      <el-icon v-if="icon" class="stats-card__icon" :size="20">
        <component :is="icon" />
      </el-icon>
    </div>
    <div class="stats-card__value">{{ formattedValue }}</div>
    <div v-if="subtitle" class="stats-card__subtitle">{{ subtitle }}</div>
    <div v-if="trend !== undefined" class="stats-card__trend" :class="trendClass">
      <span>{{ trendText }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, type Component } from 'vue'

interface Props {
  title: string
  value: number | string
  subtitle?: string
  icon?: Component
  type?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
  trend?: number
  prefix?: string
  suffix?: string
}

const props = withDefaults(defineProps<Props>(), {
  type: 'primary',
  prefix: '',
  suffix: '',
})

const formattedValue = computed(() => {
  if (typeof props.value === 'string') return props.value
  return `${props.prefix}${props.value.toLocaleString()}${props.suffix}`
})

const trendClass = computed(() => {
  /* c8 ignore next */ // trend 为 undefined 时模板 v-if 不渲染, computed 恒不被求值
  if (props.trend === undefined) return ''
  return props.trend >= 0 ? 'stats-card__trend--up' : 'stats-card__trend--down'
})

const trendText = computed(() => {
  /* c8 ignore next */ // trend 为 undefined 时模板 v-if 不渲染, computed 恒不被求值
  if (props.trend === undefined) return ''
  const sign = props.trend >= 0 ? '+' : ''
  return `${sign}${props.trend}%`
})
</script>

<style scoped>
.stats-card {
  background: var(--color-bg-card);
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.06);
  transition: box-shadow 0.3s ease;
}

.stats-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.stats-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.stats-card__title {
  font-size: 14px;
  color: var(--color-info);
}

.stats-card__icon {
  color: var(--el-color-primary);
}

.stats-card__value {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text-primary);
  margin-bottom: 8px;
}

.stats-card__subtitle {
  font-size: 12px;
  color: var(--color-info);
}

.stats-card__trend {
  font-size: 12px;
  margin-top: 8px;
}

.stats-card__trend--up {
  color: var(--color-success);
}

.stats-card__trend--down {
  color: var(--color-danger);
}

.stats-card--primary .stats-card__icon {
  color: var(--el-color-primary);
}
.stats-card--success .stats-card__icon {
  color: var(--el-color-success);
}
.stats-card--warning .stats-card__icon {
  color: var(--el-color-warning);
}
.stats-card--danger .stats-card__icon {
  color: var(--el-color-danger);
}
.stats-card--info .stats-card__icon {
  color: var(--el-color-info);
}
</style>
