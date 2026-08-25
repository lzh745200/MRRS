<template>
  <div class="list-toolbar">
    <div v-if="$slots.filters" class="list-toolbar__filters">
      <slot name="filters" />
      <el-button
        v-if="collapsible && filterCount > collapseAfter"
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
 * - slot filters: 筛选控件区（inline 排布，>collapseAfter 个时默认折叠）
 * - slot default/tools: 右侧工具组（新建/导入/导出等）
 * - collapsible: 是否启用筛选折叠（默认 true，方案规则：>3 个筛选项折叠非核心项）
 * - collapseAfter: 折叠阈值（默认 3）
 */
import { computed, ref } from 'vue'
import { ArrowDown, ArrowUp } from '@element-plus/icons-vue'

const props = withDefaults(
  defineProps<{ collapsible?: boolean; collapseAfter?: number }>(),
  { collapsible: true, collapseAfter: 3 },
)

const expanded = ref(false)
/** 由使用方在 filters slot 内通过 data-filter 标注数量；缺省按插槽子元素估算交给 CSS 收起 */
const filterCount = computed(() => {
  const attr = (getCurrentInstanceAttr() as string) || ''
  const n = Number(attr)
  return Number.isFinite(n) && n > 0 ? n : props.collapseAfter + 1
})

function getCurrentInstanceAttr() {
  // 由父组件通过 filter-count prop 显式传入更可靠
  return props.filterCount ?? ''
}

defineProps<{ filterCount?: number }>()
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
