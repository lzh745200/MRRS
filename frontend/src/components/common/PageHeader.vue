<template>
  <div class="page-header-bar">
    <!-- 返回态：左侧返回按钮 -->
    <el-button v-if="showBack" class="back-btn" link :aria-label="'返回'" @click="handleBack">
      <el-icon><ArrowLeft /></el-icon>
    </el-button>

    <div class="header-main">
      <div class="header-text">
        <h2 class="header-title">{{ title }}</h2>
        <p v-if="subtitle" class="header-subtitle">{{ subtitle }}</p>
      </div>
      <div v-if="$slots.extra || $slots.default" class="header-extra">
        <slot />
        <slot name="extra" />
      </div>
    </div>

    <!-- 度量行（可选）：统计数字/标签等次要信息 -->
    <div v-if="$slots.metrics" class="header-metrics">
      <slot name="metrics" />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * PageHeader 页头标准件（UI 精细化设计方案 v2.0 · P2 骨架）
 *
 * 契约（T1 列表页 / T2 详情页模板头部）：
 * - title 必填：页面主标题，20px/semibold
 * - subtitle：一句话说明「这页管什么」（实用性原则）
 * - showBack：详情/编辑页显示返回按钮（router.back() 或回退到 fallback）
 * - slot default/extra：右侧操作区（主操作唯一且右置）
 * - slot metrics：标题下方的度量行
 */
import { useRouter } from 'vue-router'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { ArrowLeft } from '@element-plus/icons-vue'

const props = withDefaults(
  defineProps<{
    title: string
    subtitle?: string
    showBack?: boolean
    /** 点击返回时优先跳转的路由（不传则 router.back()） */
    backTo?: string
  }>(),
  { subtitle: '', showBack: false, backTo: '' }
)

const router = useRouter()
const { pushSafe } = useRouterSafe()

function handleBack() {
  if (props.backTo) {
    pushSafe(props.backTo)
  } else if (window.history.length > 1) {
    router.back()
  }
}
</script>

<style scoped>
.page-header-bar {
  margin-bottom: var(--spacing-lg);
}

.header-main {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-md);
}

.back-btn {
  font-size: var(--font-size-lg);
  margin-right: var(--spacing-xs);
  margin-top: 2px;
  color: var(--color-text-regular);
}

.header-text {
  min-width: 0;
}

.header-title {
  margin: 0;
  font-size: var(--font-size-xxl);
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-tight);
  color: var(--color-text-primary);
}

.header-subtitle {
  margin: var(--spacing-xs) 0 0;
  font-size: var(--font-size-sm);
  color: var(--color-text-secondary);
  line-height: var(--line-height-normal);
}

.header-extra {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  flex-shrink: 0;
}

.header-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-md);
  margin-top: var(--spacing-sm);
}
</style>
