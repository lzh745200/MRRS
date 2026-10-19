<template>
  <header class="page-header">
    <div class="page-header__main">
      <h2 class="page-header__title">{{ title }}</h2>
      <p v-if="subtitle" class="page-header__subtitle">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.default || $slots.extra" class="page-header__actions">
      <slot />
      <slot name="extra" />
    </div>
  </header>
</template>

<script setup lang="ts">
/**
 * AppPageHeader 页头标准件（W23 W6 通用组件）
 *
 * props：
 * - title（必填）：页面主标题（20px / 600）
 * - subtitle（可选）：一句话说明「这页管什么」
 * slots：
 * - default：右侧主操作区
 * - extra：右侧次要操作区（与 default 并列渲染，便于「主操作唯一且右置」）
 *
 * 样式全部使用 var(--...) token，禁止硬编码色值。
 */
withDefaults(defineProps<{ title: string; subtitle?: string }>(), {
  subtitle: '',
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-lg);
}

.page-header__main {
  min-width: 0;
}

.page-header__title {
  margin: 0;
  font-size: var(--text-2xl, var(--font-size-xxl));
  font-weight: var(--font-weight-semibold);
  line-height: var(--line-height-tight);
  color: var(--color-text-primary);
}

.page-header__subtitle {
  margin: var(--spacing-xs) 0 0;
  font-size: var(--text-sm, var(--font-size-sm));
  color: var(--color-text-secondary);
  line-height: var(--leading-normal, var(--line-height-normal));
}

.page-header__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--spacing-sm);
  flex-shrink: 0;
}
</style>
