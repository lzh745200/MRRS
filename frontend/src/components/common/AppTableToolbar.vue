<template>
  <div class="app-table-toolbar">
    <div class="app-table-toolbar__lead">
      <h3 v-if="title" class="app-table-toolbar__title">{{ title }}</h3>
      <slot />
    </div>
    <div v-if="$slots.actions" class="app-table-toolbar__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * AppTableToolbar 列表工具条（W23 W6 通用组件）
 *
 * props：
 * - title（可选）：工具条左侧标题（如「筛选条件」「共 N 条」）
 * slots：
 * - default：左侧筛选控件
 * - actions：右侧批量/主操作
 *
 * 样式全部使用 var(--...) token，禁止硬编码色值。
 */
withDefaults(defineProps<{ title?: string }>(), { title: '' })
</script>

<style scoped>
.app-table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--color-bg-card);
  border: 1px solid var(--color-card-border, var(--color-border-light));
  border-radius: var(--radius-card, var(--radius-lg));
  margin-bottom: var(--spacing-md);
}

.app-table-toolbar__lead {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
  min-width: 0;
}

.app-table-toolbar__title {
  margin: 0;
  font-size: var(--text-md, var(--font-size-md));
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.app-table-toolbar__actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}
</style>
