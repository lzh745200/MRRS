<template>
  <div class="page-container">
    <!-- 页面头部 -->
    <div v-if="title || $slots.header" class="page-header">
      <div class="header-left">
        <h2 class="page-title">{{ title }}</h2>
        <p v-if="description" class="page-description">{{ description }}</p>
      </div>
      <div class="header-right">
        <slot name="header-actions"></slot>
      </div>
    </div>

    <!-- 搜索/筛选区域 -->
    <div v-if="$slots.filter" class="filter-section">
      <slot name="filter"></slot>
    </div>

    <!-- 主要内容 -->
    <div class="main-section">
      <slot></slot>
    </div>

    <!-- 底部区域 -->
    <div v-if="$slots.footer" class="footer-section">
      <slot name="footer"></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  title?: string
  description?: string
}>()
</script>

<style scoped>
.page-container {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #e8e8e8;
}

.header-left {
  flex: 1;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(----color-primary-dark-1);
  margin: 0 0 4px 0;
}

.page-description {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}

.header-right {
  display: flex;
  gap: 12px;
  align-items: center;
}

.filter-section {
  background: white;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
}

.main-section {
  flex: 1;
  background: white;
  padding: 20px;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  overflow: auto;
}

.footer-section {
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #e8e8e8;
}
</style>
