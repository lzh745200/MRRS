<template>
  <div class="app-empty" role="status">
    <svg class="app-empty__icon" viewBox="0 0 48 48" fill="none" aria-hidden="true">
      <rect x="6" y="10" width="36" height="28" rx="4" stroke="currentColor" stroke-width="2" />
      <path d="M6 18h36" stroke="currentColor" stroke-width="2" />
      <path d="M18 30h12" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
    </svg>
    <p class="app-empty__text">{{ text }}</p>
    <p v-if="description" class="app-empty__desc">{{ description }}</p>
    <div v-if="$slots.default" class="app-empty__action">
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * AppEmpty 空态三件套之一（W23 W6 通用组件）
 *
 * 与 `styles/components/states.scss` 的全局约定对齐：
 * `.app-empty__icon` / `.app-empty__text` / `.app-empty__desc` / `.app-empty__action`。
 *
 * props：
 * - text（可选）：空态主文案，默认「暂无数据」
 * - description（可选）：补充说明
 * slots：
 * - default：空态下的引导操作（如「新增」「去筛选」）
 *
 * 样式全部使用 var(--...) token，禁止硬编码色值。
 */
withDefaults(defineProps<{ text?: string; description?: string }>(), {
  text: '暂无数据',
  description: '',
})
</script>

<style scoped>
.app-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xl) var(--spacing-md);
  text-align: center;
  color: var(--color-text-secondary);
}

.app-empty__icon {
  width: 40px;
  height: 40px;
  color: var(--color-text-placeholder);
}

.app-empty__text {
  margin: 0;
  font-size: var(--text-md, var(--font-size-md));
  font-weight: var(--font-weight-medium);
  color: var(--color-text-regular);
}

.app-empty__desc {
  max-width: 520px;
  margin: 0;
  font-size: var(--text-sm, var(--font-size-sm));
  color: var(--color-text-placeholder);
  line-height: var(--line-height-normal);
}

.app-empty__action {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-top: var(--spacing-sm);
}
</style>
