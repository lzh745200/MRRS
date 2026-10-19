<template>
  <div class="app-error" role="alert">
    <span class="app-error__icon" aria-hidden="true">!</span>
    <p class="app-error__message">{{ message }}</p>
    <button type="button" class="app-error__retry" @click="emit('retry')">重试</button>
  </div>
</template>

<script setup lang="ts">
/**
 * AppError 错误态三件套之一（W23 W6 通用组件）
 *
 * 与 `styles/components/states.scss` 的全局约定对齐：
 * `.app-error__icon` / `.app-error__message` / `.app-error__retry`（可重试，禁止静默失败）。
 *
 * props：
 * - message（可选）：错误文案，默认「加载失败，请稍后重试」
 * emits：
 * - retry：点击「重试」按钮时触发（由使用方重新发起加载）
 *
 * 样式全部使用 var(--...) token，禁止硬编码色值。
 */
withDefaults(defineProps<{ message?: string }>(), {
  message: '加载失败，请稍后重试',
})

const emit = defineEmits<{ (e: 'retry'): void }>()
</script>

<style scoped>
.app-error {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-xl) var(--spacing-md);
  text-align: center;
  color: var(--color-text-secondary);
}

.app-error__icon {
  color: var(--color-danger);
  font-size: var(--font-size-display);
  font-weight: var(--font-weight-bold);
  line-height: var(--line-height-none);
}

.app-error__message {
  margin: 0;
  font-size: var(--text-md, var(--font-size-md));
  font-weight: var(--font-weight-medium);
  color: var(--color-text-regular);
}

.app-error__retry {
  margin-top: var(--spacing-sm);
  height: var(--control-height-sm);
  padding: 0 var(--spacing-md);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-control, var(--radius-md));
  background: var(--color-bg-card);
  color: var(--color-primary);
  font-size: var(--text-sm, var(--font-size-sm));
  cursor: pointer;
  transition: background-color var(--transition-fast);
}

.app-error__retry:hover {
  background: var(--color-primary-50, var(--color-primary-light-8));
}
</style>
