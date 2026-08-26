<template>
  <span class="fund-guide-popover">
    <el-popover placement="top" :width="280" trigger="hover" :show-after="150">
      <template #reference>
        <el-icon class="guide-icon" aria-label="操作指引"><QuestionFilled /></el-icon>
      </template>
      <div class="guide-body">
        <div class="guide-title">{{ title }}</div>
        <div class="guide-section"><span class="guide-label">前置条件</span>{{ precondition }}</div>
        <div class="guide-section"><span class="guide-label">后续影响</span>{{ impact }}</div>
        <div class="guide-section"><span class="guide-label">下一步</span>{{ nextStep }}</div>
      </div>
    </el-popover>
  </span>
</template>

<script setup lang="ts">
import { QuestionFilled } from '@element-plus/icons-vue'

defineProps<{
  title: string
  precondition: string
  impact: string
  nextStep: string
}>()
</script>

<style scoped>
.guide-icon {
  margin-left: 6px;
  color: var(--el-color-primary);
  cursor: help;
  vertical-align: middle;
}
.guide-body {
  font-size: 12px;
  line-height: 1.6;
}
.guide-title {
  font-weight: 600;
  margin-bottom: 6px;
  color: var(--el-text-color-primary);
}
.guide-section {
  margin-bottom: 4px;
  color: var(--el-text-color-regular);
}
.guide-label {
  display: inline-block;
  min-width: 56px;
  color: var(--el-color-primary);
  font-weight: 500;
}
</style>
