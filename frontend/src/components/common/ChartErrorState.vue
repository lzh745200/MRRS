<template>
  <div class="chart-error-state">
    <el-alert type="error" :closable="false" show-icon :title="message || '数据加载失败'" />
    <el-button size="small" type="primary" link :loading="retrying" @click="handleRetry">
      <el-icon style="margin-right: 4px"><RefreshRight /></el-icon>重试
    </el-button>
  </div>
</template>

<script setup lang="ts">
/**
 * 图表/数据区域的内联错误状态组件。
 *
 * 设计约定（2026-08-14）：后台数据加载失败不再弹全局 toast，
 * 而是在内容区域展示错误原因 + 重试按钮，用户可以就地恢复。
 */
import { ref } from 'vue'
import { RefreshRight } from '@element-plus/icons-vue'

defineProps<{
  message?: string
}>()

const emit = defineEmits<{
  retry: []
}>()

const retrying = ref(false)

async function handleRetry() {
  if (retrying.value) return
  retrying.value = true
  try {
    emit('retry')
    // 父组件负责执行重试（异步加载函数）；短暂延时后复位按钮状态
    await new Promise((resolve) => setTimeout(resolve, 400))
  } finally {
    retrying.value = false
  }
}
</script>

<style scoped>
.chart-error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  min-height: 200px;
  padding: 20px;
}
</style>
