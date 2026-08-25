<template>
  <div class="list-toolbar">
    <div v-if="$slots.filters" class="list-toolbar__filters">
      <slot name="filters" />
      <el-button
        v-if="collapsible && (filterCount ?? 0) > collapseAfter"
        link
        type="primary"
        size="small"
        @click="expanded = !expanded"
      >
        {{ expanded ? '收起' : `展开全部(${filterCount})` }}
        <el-icon><component :is="expanded ? ArrowUp : ArrowDown" /></el-icon>
      </el-button>
    </div>
    <div v-if="$slots.tools || $slots.default" class="list-toolbar__tools">
      <slot />
      <slot name="tools" />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * ListToolbar 列表工具栏标准件（UI 精细化设计方案 v2.0 · P2 骨架）
 *
 * 契约（T1 列表页模板 · PageHeader 之下、Table 卡片之上）：
 * - slot filters: 筛选控件区（inline 排布）
 * - slot default/tools: 右侧工具组（新建/导入/导出等，唯一主钮右置）
 * - collapsible + collapseAfter + filterCount:
 *     方案规则「>3 个筛选项折叠非核心项」——使用方传 filterCount（筛选项总数），
 *     超过 collapseAfter(3) 时出现展开/收起切换；折叠态由 CSS 类控制非核心项。
 */
import { ref } from 'vue'
import { ArrowDown, ArrowUp } from '@element-plus/icons-vue'

withDefaults(
  defineProps<{
    collapsible?: boolean
    /** 筛选项总数（用于决定是否显示折叠开关） */
    filterCount?: number
    collapseAfter?: number
  }>(),
  { collapsible: true, filterCount: 0, collapseAfter: 3 },
)

const expanded = ref(false)

defineExpose({ expanded })
</script>

<style scoped lang="scss">
.list-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3, 12px);
  margin-bottom: var(--space-3, 12px);
}
.list-toolbar__filters {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2, 8px);
  flex: 1 1 auto;
  min-width: 0;
}
.list-toolbar__tools {
  display: flex;
  align-items: center;
  gap: var(--space-2, 8px);
  flex: 0 0 auto;
}
</style>
