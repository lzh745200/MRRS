<template>
  <div
    class="kpi-card"
    :class="[`theme-${theme}`, { 'is-clickable': !!to }]"
    :role="to ? 'button' : undefined"
    :tabindex="to ? 0 : undefined"
    @click="handleClick"
    @keydown.enter.prevent="handleClick"
  >
    <div v-if="$slots.icon || icon" class="kpi-card__icon">
      <slot name="icon">
        <el-icon><component :is="icon" /></el-icon>
      </slot>
    </div>
    <div class="kpi-card__content">
      <div class="kpi-card__label">{{ label }}</div>
      <div class="kpi-card__value">
        <span class="kpi-card__number">{{ displayValue }}</span>
        <span v-if="unit" class="kpi-card__unit">{{ unit }}</span>
      </div>
      <div v-if="trend !== undefined && trend !== null" class="kpi-card__trend" :class="trendClass">
        <el-icon class="kpi-card__trend-icon"><component :is="trendIcon" /></el-icon>
        <span v-if="trend !== 0">{{ Math.abs(trend) }}%</span>
        <template v-else>持平</template>
        <span v-if="trendLabel" class="kpi-card__trend-label">{{ trendLabel }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * KpiCard 统计卡标准件（UI 精细化设计方案 v2.0 · P2 骨架）
 *
 * 从 dashboard/KpiCards.vue 抽取的纯展示单卡，供各仪表盘复用：
 * - 数值：24px semibold + 等宽数字（tabular-nums）
 * - 同比趋势：正=success 上箭头 / 负=danger 下箭头 / 0=info 持平
 *   （invertTrend 用于「越低越好」指标如异常数/超期数）
 * - 图标容器：40px 圆角 primary-light-8 底
 * - theme: primary/success/warning/danger/info 语义色变体
 */
import { computed } from 'vue'
import { Top, Bottom, Minus } from '@element-plus/icons-vue'
import { useRouterSafe } from '@/composables/useRouterSafe'

const props = withDefaults(
  defineProps<{
    label: string
    value?: number | string | null
    unit?: string
    /** 同比百分点；undefined/null 不渲染趋势行 */
    trend?: number | null
    /** 趋势说明文案（如「较上月」） */
    trendLabel?: string
    /** 「越低越好」指标反转语义色（负向指标下降显示绿色） */
    invertTrend?: boolean
    icon?: unknown
    /** 点击跳转路由（可选） */
    to?: string
    /** 语义色主题 */
    theme?: 'primary' | 'success' | 'warning' | 'danger' | 'info'
  }>(),
  {
    value: null,
    unit: '',
    trend: undefined,
    trendLabel: '',
    invertTrend: false,
    icon: undefined,
    to: '',
    theme: 'primary',
  }
)

const { pushSafe } = useRouterSafe()

const displayValue = computed(() => {
  if (props.value === null || props.value === undefined) return '--'
  return typeof props.value === 'number' ? props.value.toLocaleString('zh-CN') : props.value
})

/** 负向指标反转后，「上升」对用户而言是坏事 → danger */
const effectiveRising = computed(() =>
  props.invertTrend ? (props.trend ?? 0) < 0 : (props.trend ?? 0) > 0
)

const trendClass = computed(() => {
  const t = props.trend ?? 0
  if (t === 0) return 'is-flat'
  return effectiveRising.value ? 'is-up' : 'is-down'
})

const trendIcon = computed(() => {
  const t = props.trend ?? 0
  if (t === 0) return Minus
  return effectiveRising.value ? Top : Bottom
})

function handleClick() {
  if (props.to) pushSafe(props.to)
}
</script>

<style scoped>
.kpi-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-lg);
  background: var(--color-bg-card);
  border: 1px solid var(--color-border-light);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-card);
}

.kpi-card.is-clickable {
  cursor: pointer;
}

.kpi-card__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: 10px;
  font-size: var(--font-size-xl);
  background: var(--color-primary-light-8);
  color: var(--color-primary);
  flex-shrink: 0;
}

.kpi-card.theme-success .kpi-card__icon {
  background: var(--color-success-light-9, #f0f9eb);
  color: var(--color-success);
}

.kpi-card.theme-warning .kpi-card__icon {
  background: var(--color-warning-light-9, #fdf6ec);
  color: var(--color-warning);
}

.kpi-card.theme-danger .kpi-card__icon {
  background: var(--color-danger-light-9, #fef0f0);
  color: var(--color-danger);
}

.kpi-card.theme-info .kpi-card__icon {
  background: var(--color-info-light-9, #f4f4f5);
  color: var(--color-info);
}

.kpi-card__content {
  min-width: 0;
}

.kpi-card__label {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: var(--line-height-snug);
}

.kpi-card__value {
  display: flex;
  align-items: baseline;
  gap: var(--spacing-xs);
}

.kpi-card__number {
  font-family: var(--font-family-mono);
  font-variant-numeric: tabular-nums;
  font-size: var(--font-size-xxxl);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-tight);
  color: var(--color-text-primary);
}

.kpi-card__unit {
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
}

.kpi-card__trend {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-top: 2px;
  font-size: var(--font-size-xs);
}

.kpi-card__trend.is-up {
  color: var(--color-success);
}

.kpi-card__trend.is-down {
  color: var(--color-danger);
}

.kpi-card__trend.is-flat {
  color: var(--color-text-secondary);
}

.kpi-card__trend-icon {
  font-size: 14px;
}

.kpi-card__trend-label {
  color: var(--color-text-secondary);
}
</style>
