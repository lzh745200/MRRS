<template>
  <div class="empty-state" :data-type="type">
    <el-empty :description="resolvedText" :image-size="size">
      <template v-if="action" #default>
        <el-button type="primary" size="small" @click="$emit('action')">{{ action }}</el-button>
      </template>
    </el-empty>
  </div>
</template>

<script setup lang="ts">
/**
 * EmptyState 空态标准件（UI 精细化设计方案 v2.0 · P2 骨架）
 *
 * 契约（T1 列表页 / T4 仪表盘空数据场景唯一空态出口）：
 * - type:    no-data(默认·暂无数据) | no-search(未找到匹配结果) |
 *            no-permission(无权访问) | error(加载失败)
 * - text:    覆盖默认文案
 * - action:  行动按钮文案；提供时点击触发 action 事件
 * - size:    el-empty image-size 透传
 */
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    type?: 'no-data' | 'no-search' | 'no-permission' | 'error'
    text?: string
    action?: string
    size?: number
  }>(),
  { type: 'no-data', text: '', action: '', size: 96 },
)

defineEmits<{ (e: 'action'): void }>()

const DEFAULT_TEXT: Record<string, string> = {
  'no-data': '暂无数据',
  'no-search': '未找到匹配结果',
  'no-permission': '暂无访问权限',
  error: '加载失败，请稍后重试',
}

const resolvedText = computed(() => props.text || DEFAULT_TEXT[props.type] || '暂无数据')
</script>

<style scoped lang="scss">
.empty-state {
  padding: var(--space-4, 16px) 0;
}
</style>
