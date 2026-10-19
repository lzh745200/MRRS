<template>
  <div class="app-stat-card" :class="`app-stat-card--${tone}`">
    <span v-if="$slots.icon" class="app-stat-card__icon"><slot name="icon" /></span>
    <div class="app-stat-card__body">
      <span class="app-stat-card__label">{{ label }}</span>
      <div class="app-stat-card__value">
        <span class="kpi-value">{{ value }}</span>
        <span v-if="unit" class="app-stat-card__unit">{{ unit }}</span>
        <span
          v-if="trend"
          class="stat-trend"
          :class="trend === 'up' ? 'is-up' : 'is-down'"
          :title="trendText"
          :aria-label="trendText"
        >
          {{ trendText }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * AppStatCard 统计卡（W23 W6 通用组件）
 *
 * 与 `styles/components/card.scss` 的全局约定对齐：
 * `.app-stat-card > .app-stat-card__icon? + .app-stat-card__body`，
 * 数字用 `.kpi-value`（tabular-nums），趋势用 `.stat-trend.is-up/.is-down`
 * （简化模式下由 `[data-simplify="true"] .stat-trend` 全局隐藏）。
 *
 * props：
 * - label（必填）：指标名称
 * - value（必填）：指标值（数字或已格式化字符串）
 * - unit（可选）：单位（人 / 万元 / % 等）
 * - trend（可选）：'up' | 'down' | null，趋势箭头
 * - tone（可选）：primary / success / warning / danger，默认 primary
 * slots：
 * - icon：指标图标
 *
 * 样式全部使用 var(--...) token，禁止硬编码色值。
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    label: string
    value: string | number
    unit?: string
    trend?: 'up' | 'down' | null
    tone?: 'primary' | 'success' | 'warning' | 'danger'
  }>(),
  { unit: '', trend: null, tone: 'primary' }
)

/** 趋势文案（同时作为 title/aria-label，保证可访问性） */
const trendText = computed(() => (props.trend === 'up' ? '↑ 上升' : '↓ 下降'))
</script>

<style scoped>
.app-stat-card {
  --stat-tone: var(--color-primary);

  display: flex;
  align-items: flex-start;
  gap: var(--spacing-md);
  min-height: 96px;
  padding: var(--spacing-md) var(--spacing-lg);
  background: var(--color-bg-card);
  border: 1px solid var(--color-card-border, var(--color-border-light));
  border-radius: var(--radius-card, var(--radius-lg));
  box-shadow: var(--shadow-card);
  transition: box-shadow var(--transition-fast);
}

.app-stat-card:hover {
  box-shadow: var(--shadow-pop, var(--shadow-card-hover));
}

.app-stat-card--success {
  --stat-tone: var(--color-success);
}

.app-stat-card--warning {
  --stat-tone: var(--color-warning);
}

.app-stat-card--danger {
  --stat-tone: var(--color-danger);
}

.app-stat-card__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: none;
  width: var(--icon-size-xl);
  height: var(--icon-size-xl);
  border-radius: var(--radius-control, var(--radius-md));
  background: var(--color-primary-50, var(--color-primary-light-8));
  color: var(--stat-tone);
  font-size: var(--text-xl, var(--font-size-xl));
}

.app-stat-card__body {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  min-width: 0;
}

.app-stat-card__label {
  font-size: var(--text-sm, var(--font-size-sm));
  color: var(--color-text-secondary);
  line-height: var(--line-height-tight);
}

.app-stat-card__value {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: var(--spacing-xs);
}

.kpi-value {
  font-size: calc(28px * var(--font-scale, 1));
  font-weight: var(--font-weight-bold);
  font-variant-numeric: tabular-nums;
  line-height: var(--line-height-tight);
  color: var(--stat-tone);
}

.app-stat-card__unit {
  font-size: var(--text-sm, var(--font-size-sm));
  color: var(--color-text-secondary);
}

.stat-trend {
  font-size: var(--text-xs, var(--font-size-xs));
  font-variant-numeric: tabular-nums;
}

.stat-trend.is-up {
  color: var(--color-success);
}

.stat-trend.is-down {
  color: var(--color-danger);
}
</style>
