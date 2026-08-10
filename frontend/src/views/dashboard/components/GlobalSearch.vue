<template>
  <div
    class="global-search"
    @keydown.down.prevent="moveDown"
    @keydown.up.prevent="moveUp"
    @keydown.enter.prevent="selectCurrent"
  >
    <el-input
      ref="inputRef"
      v-model="keyword"
      :placeholder="placeholder"
      :prefix-icon="Search"
      clearable
      class="search-input"
      @input="onInput"
      @focus="onFocus"
      @blur="onBlur"
    >
      <template #suffix>
        <el-icon v-if="loading" class="is-loading"><Loading /></el-icon>
      </template>
    </el-input>

    <!-- 搜索结果下拉 -->
    <transition name="el-zoom-in-top">
      <div v-show="showDropdown && (results.length > 0 || showNoResult)" class="search-dropdown">
        <!-- 无结果 -->
        <div v-if="results.length === 0 && showNoResult && !loading" class="no-result">
          <el-icon><Search /></el-icon>
          <span>未找到 "{{ trimmedKeyword }}" 相关结果</span>
        </div>

        <!-- 结果列表 -->
        <template v-for="group in groupedResults" :key="group.type">
          <div v-if="group.items.length > 0" class="result-group">
            <div class="group-label">
              {{ group.label }}
              <el-tag size="small" type="info" effect="plain" round>{{
                group.items.length
              }}</el-tag>
            </div>
            <div
              v-for="item in group.items"
              :key="`${item.type}-${item.id}`"
              class="result-item"
              :class="{ active: activeIndex === flatIndex(item) }"
              @mousedown.prevent="onItemClick(item)"
              @mouseenter="activeIndex = flatIndex(item)"
            >
              <el-icon class="item-icon"><component :is="iconMap[item.type]" /></el-icon>
              <div class="item-content">
                <div class="item-title">{{ item.title }}</div>
                <div v-if="item.subtitle" class="item-subtitle">{{ item.subtitle }}</div>
              </div>
              <el-icon class="item-arrow"><ArrowRight /></el-icon>
            </div>
          </div>
        </template>

        <!-- 底部提示 -->
        <div v-if="results.length > 0" class="dropdown-footer">
          <span>共 {{ total }} 条结果</span>
          <span class="hint">↑↓ 选择 · Enter 跳转</span>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import {
  Search,
  Loading,
  ArrowRight,
  House,
  Document,
  Tickets,
  School,
  UserFilled,
} from '@element-plus/icons-vue'
import { globalSearch, SEARCH_TYPE_LABELS, type SearchItem } from '@/api/search'
import { useRouterSafe } from '@/composables/useRouterSafe'

withDefaults(
  defineProps<{
    placeholder?: string
  }>(),
  {
    placeholder: '搜索帮扶村、项目、学校、政策…',
  }
)

const { pushSafe } = useRouterSafe()

const keyword = ref('')
const trimmedKeyword = ref('')
const results = ref<SearchItem[]>([])
const total = ref(0)
const loading = ref(false)
const showDropdown = ref(false)
const showNoResult = ref(false)
const activeIndex = ref(-1)
const inputRef = ref()

// 防抖定时器
let debounceTimer: ReturnType<typeof setTimeout> | null = null
// 延迟关闭定时器（避免 click 事件丢失）
let blurTimer: ReturnType<typeof setTimeout> | null = null

// 类型 → 图标组件映射
const iconMap: Record<string, any> = {
  village: House,
  project: Document,
  policy: Tickets,
  school: School,
  user: UserFilled,
}

// 按类型分组结果
const groupedResults = computed(() => {
  const groups: { type: SearchItem['type']; label: string; items: SearchItem[] }[] = []
  const typeOrder: SearchItem['type'][] = ['village', 'project', 'school', 'policy', 'user']
  for (const type of typeOrder) {
    const items = results.value.filter((r) => r.type === type)
    if (items.length > 0) {
      groups.push({ type, label: SEARCH_TYPE_LABELS[type], items })
    }
  }
  return groups
})

// 计算某 item 在扁平列表中的索引
function flatIndex(item: SearchItem): number {
  return results.value.indexOf(item)
}

// 输入处理（防抖 300ms）
function onInput() {
  showNoResult.value = false
  if (debounceTimer) {
    clearTimeout(debounceTimer)
  }
  const q = keyword.value.trim()
  if (!q) {
    results.value = []
    total.value = 0
    showDropdown.value = false
    return
  }
  showDropdown.value = true
  debounceTimer = setTimeout(() => doSearch(q), 300)
}

async function doSearch(q: string) {
  loading.value = true
  activeIndex.value = -1
  try {
    const res = await globalSearch(q, 20)
    results.value = res.items
    total.value = res.total
    trimmedKeyword.value = q
    showNoResult.value = true
  } catch {
    results.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

function onFocus() {
  if (blurTimer) {
    clearTimeout(blurTimer)
    blurTimer = null
  }
  if (keyword.value.trim()) {
    showDropdown.value = true
  }
}

function onBlur() {
  // 延迟关闭，让 mousedown click 有时间触发
  blurTimer = setTimeout(() => {
    showDropdown.value = false
  }, 200)
}

// 点击结果项
function onItemClick(item: SearchItem) {
  showDropdown.value = false
  pushSafe(item.link)
}

// 键盘导航
function moveDown() {
  if (results.value.length === 0) return
  activeIndex.value = Math.min(activeIndex.value + 1, results.value.length - 1)
}
function moveUp() {
  if (results.value.length === 0) return
  activeIndex.value = Math.max(activeIndex.value - 1, 0)
}
function selectCurrent() {
  if (activeIndex.value >= 0 && activeIndex.value < results.value.length) {
    onItemClick(results.value[activeIndex.value])
  }
}

// 清理
onUnmounted(() => {
  if (debounceTimer) clearTimeout(debounceTimer)
  if (blurTimer) clearTimeout(blurTimer)
})
</script>

<style scoped lang="scss">
.global-search {
  position: relative;
  width: 100%;
  max-width: 480px;
}

.search-input {
  :deep(.el-input__wrapper) {
    border-radius: 20px;
    box-shadow: 0 0 0 1px #dcdfe6;
    transition: box-shadow 0.2s;
    &:hover {
      box-shadow: 0 0 0 1px #c0c4cc;
    }
    &.is-focus {
      box-shadow: 0 0 0 2px #409eff;
    }
  }
  :deep(.el-input__inner) {
    height: 38px;
  }
}

.search-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  right: 0;
  z-index: 2050;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.12);
  max-height: 420px;
  overflow-y: auto;
  border: 1px solid #ebeef5;
}

.no-result {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 24px 20px;
  color: #909399;
  font-size: 14px;
  justify-content: center;
}

.result-group {
  padding: 4px 0;
  &:not(:last-child) {
    border-bottom: 1px solid #f5f7fa;
  }
}

.group-label {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px 4px;
  font-size: 12px;
  font-weight: 600;
  color: #909399;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.result-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 16px;
  cursor: pointer;
  transition: background 0.15s;
  &:hover,
  &.active {
    background: #f0f5ff;
  }
  &.active {
    .item-title {
      color: #409eff;
    }
  }
}

.item-icon {
  font-size: 16px;
  color: #909399;
  flex-shrink: 0;
}

.item-content {
  flex: 1;
  min-width: 0;
}

.item-title {
  font-size: 14px;
  color: #303133;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-subtitle {
  font-size: 12px;
  color: #909399;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 2px;
}

.item-arrow {
  font-size: 12px;
  color: #c0c4cc;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.15s;
}
.result-item:hover .item-arrow,
.result-item.active .item-arrow {
  opacity: 1;
}

.dropdown-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  font-size: 12px;
  color: #909399;
  border-top: 1px solid #f5f7fa;
  .hint {
    font-size: 11px;
  }
}
</style>
