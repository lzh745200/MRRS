<template>
  <div class="app-loading" role="status" aria-live="polite" aria-busy="true">
    <div v-for="row in rows" :key="row" class="app-loading__row" />
    <span class="app-loading__text">加载中…</span>
  </div>
</template>

<script setup lang="ts">
/**
 * AppLoading 加载态三件套之一（W23 W6 通用组件）
 *
 * 与 `styles/components/states.scss` 的全局约定对齐：骨架行为 `.app-loading__row`
 * （全局提供 shimmer 动画，`prefers-reduced-motion` 下自动关闭）。
 *
 * props：
 * - rows（可选）：骨架行数，默认 3；0 时只保留加载文案
 *
 * 样式全部使用 var(--...) token，禁止硬编码色值。
 */
withDefaults(defineProps<{ rows?: number }>(), { rows: 3 })
</script>

<style scoped>
.app-loading {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: var(--spacing-sm);
  padding: var(--spacing-lg);
  color: var(--color-text-secondary);
  text-align: center;
}

.app-loading__row {
  height: var(--icon-size-md);
  border-radius: var(--radius-pill, var(--radius-round));
  background: linear-gradient(
    90deg,
    var(--color-border-lighter) 25%,
    var(--color-bg-hover) 37%,
    var(--color-border-lighter) 63%
  );
  background-size: 400% 100%;
  animation: app-loading-shimmer 1.4s ease infinite;
}

.app-loading__text {
  font-size: var(--text-xs, var(--font-size-xs));
  color: var(--color-text-secondary);
}

@keyframes app-loading-shimmer {
  0% {
    background-position: 100% 50%;
  }

  100% {
    background-position: 0 50%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .app-loading__row {
    animation: none;
  }
}
</style>
