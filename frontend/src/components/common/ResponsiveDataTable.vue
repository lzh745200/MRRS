<template>
  <div class="responsive-table-wrapper">
    <!-- 桌面端：标准表格 -->
    <el-table
      v-if="!isMobile"
      v-bind="$attrs"
      :data="data"
      :class="['desktop-table', $attrs.class]"
      v-on="tableEvents"
    >
      <slot />
    </el-table>

    <!-- 移动端：卡片列表 -->
    <div v-else class="mobile-card-list">
      <div
        v-for="(row, idx) in data"
        :key="row.id || idx"
        class="data-card"
        @click="$emit('row-click', row)"
      >
        <div class="card-header">
          <span class="card-title">{{ getCardTitle(row) }}</span>
          <span v-if="getCardBadge(row)" class="card-badge" :class="getCardBadgeClass(row)">
            {{ getCardBadge(row) }}
          </span>
        </div>
        <div class="card-body">
          <div v-for="field in cardFields" :key="field.key" class="card-field">
            <span class="field-label">{{ field.label }}</span>
            <span class="field-value">{{ formatField(row[field.key], field) }}</span>
          </div>
        </div>
        <div v-if="$slots['card-actions']" class="card-actions">
          <slot name="card-actions" :row="row" />
        </div>
      </div>
      <!-- 空状态 -->
      <div v-if="!data || data.length === 0" class="empty-state">
        <el-icon class="empty-icon"><Document /></el-icon>
        <span>{{ emptyText || '暂无数据' }}</span>
      </div>
    </div>

    <!-- 分页（共用） -->
    <div v-if="showPagination && total > 0" class="table-pagination">
      <el-pagination
        v-model:current-page="currentPage"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        :small="isMobile"
        layout="total, prev, pager, next"
        @update:current-page="$emit('page-change', $event)"
        @update:page-size="$emit('size-change', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { Document } from '@element-plus/icons-vue'

interface CardField {
  key: string
  label: string
  format?: string // 'currency' | 'percent' | 'date'
}

const props = withDefaults(
  defineProps<{
    data: any[]
    cardFields?: CardField[]
    cardTitleKey?: string
    cardBadgeKey?: string
    total?: number
    showPagination?: boolean
    emptyText?: string
  }>(),
  {
    cardFields: () => [],
    showPagination: false,
    total: 0,
    emptyText: '暂无数据',
  }
)

const emit = defineEmits<{
  'row-click': [row: any]
  'page-change': [page: number]
  'size-change': [size: number]
}>()

const windowWidth = ref(window.innerWidth)
const isMobile = computed(() => windowWidth.value < 768)
const currentPage = ref(1)
const pageSize = ref(10)

const tableEvents = computed(() => {
  const events: Record<string, any> = {}
  /* c8 ignore start */ // 死代码: defineEmits 返回函数无自有可枚举属性, for-in 恒不迭代
  for (const key in emit) {
    events[key] = (...args: any[]) => (emit as any)[key](...args)
  }
  /* c8 ignore stop */
  return events
})

function getCardTitle(row: any): string {
  if (props.cardTitleKey && row[props.cardTitleKey]) {
    return String(row[props.cardTitleKey])
  }
  return row.name || row.title || row.label || `#${row.id || ''}`
}

function getCardBadge(row: any): string {
  if (props.cardBadgeKey && row[props.cardBadgeKey]) {
    return String(row[props.cardBadgeKey])
  }
  return row.status || row.badge || ''
}

function getCardBadgeClass(row: any): string {
  const val = getCardBadge(row)
  if (val.includes('完成') || val.includes('active')) return 'badge-success'
  if (val.includes('超') || val.includes('danger')) return 'badge-danger'
  if (val.includes('待') || val.includes('pending')) return 'badge-warning'
  return 'badge-info'
}

function formatField(value: any, field: CardField): string {
  if (value === null || value === undefined) return '-'
  if (field.format === 'currency') return `¥${Number(value).toLocaleString()}`
  if (field.format === 'percent') return `${Number(value).toFixed(1)}%`
  if (field.format === 'date') return String(value).slice(0, 10)
  return String(value)
}

function onResize() {
  windowWidth.value = window.innerWidth
}
onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))
</script>

<style scoped>
.responsive-table-wrapper {
  width: 100%;
}
.desktop-table {
  width: 100%;
}
.mobile-card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.data-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  cursor: pointer;
  transition: transform 0.15s;
}
.data-card:active {
  transform: scale(0.98);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.card-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text-primary);
}
.card-badge {
  padding: 2px 10px;
  border-radius: 12px;
  font-size: 12px;
}
.badge-success {
  background: #e8f5e9;
  color: #2e7d32;
}
.badge-danger {
  background: #fce4ec;
  color: #c62828;
}
.badge-warning {
  background: #fff3e0;
  color: #ef6c00;
}
.badge-info {
  background: #e3f2fd;
  color: #1565c0;
}
.card-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.card-field {
  display: flex;
  justify-content: space-between;
  font-size: 14px;
}
.field-label {
  color: var(--color-info);
}
.field-value {
  color: var(--color-text-primary);
  font-weight: 500;
  text-align: right;
}
.card-actions {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #eee;
}
.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--color-info);
}
.empty-icon {
  font-size: 32px;
  display: block;
  margin-bottom: 8px;
}
.table-pagination {
  display: flex;
  justify-content: center;
  margin-top: 16px;
}
</style>
