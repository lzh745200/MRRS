<template>
  <el-dialog
    v-model="visible"
    title="菜单搜索"
    width="560px"
    class="menu-search-dialog"
    append-to-body
    destroy-on-close
  >
    <div class="menu-search">
      <el-input
        v-model="keyword"
        class="menu-search-input"
        placeholder="搜索菜单名称 / key / 路径"
        clearable
      >
        <template #prefix>
          <el-icon><Search /></el-icon>
        </template>
      </el-input>

      <div v-if="groups.length" class="menu-search-list">
        <div v-for="group in groups" :key="group.title" class="menu-search-group">
          <div class="menu-search-group-title">{{ group.title }}</div>
          <button
            v-for="entry in group.entries"
            :key="entry.key"
            type="button"
            class="menu-search-item"
            :class="{ 'is-active': entry.index === activeIndex }"
            @click="choose(entry)"
            @mouseenter="activeIndex = entry.index"
          >
            <el-icon class="menu-search-item-icon">
              <component :is="resolveMenuIcon(entry.icon)" />
            </el-icon>
            <span class="menu-search-item-label">{{ entry.label }}</span>
            <span v-if="entry.sectionLabel" class="menu-search-item-section">{{
              entry.sectionLabel
            }}</span>
            <span
              class="menu-search-item-star"
              :class="{ 'is-starred': isFavorite(entry.key) }"
              role="button"
              tabindex="0"
              aria-label="收藏或取消收藏"
              @click.stop="toggleFavoriteEntry(entry)"
            >
              <el-icon>
                <StarFilled v-if="isFavorite(entry.key)" />
                <Star v-else />
              </el-icon>
            </span>
          </button>
        </div>
      </div>
      <el-empty v-else :description="emptyHint" :image-size="72" />
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * 菜单搜索弹窗（Ctrl+K 打开）
 *
 * - 搜索范围：menuStore.flatEntries（工作台 + 各板块 page / group children / console）
 * - 匹配规则：label / key / path 大小写不敏感子串
 * - 空关键词展示「收藏」+「最近访问」（localStorage，上限 8；损坏数据回退空）
 * - 键盘：↑/↓ 移动高亮、Enter 跳转、Esc 关闭
 */
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { Search, Star, StarFilled } from '@element-plus/icons-vue'
import { useMenuStore, type FlatMenuEntry } from '@/stores/menu'
import { useRouterSafe } from '@/composables/useRouterSafe'
import { useMenuFavorites } from '@/composables/useMenuFavorites'
import { useRecentMenus, type NavMenuRecord } from '@/composables/useRecentMenus'
import { resolveMenuIcon } from '@/components/nav/menuIcons'

/** 弹窗显隐（父组件 v-model） */
const visible = defineModel<boolean>({ default: false })

/** 搜索结果条目（index 为可选中列表的全局序号，用于键盘高亮） */
interface SearchEntry {
  key: string
  label: string
  path: string
  icon?: string
  sectionLabel?: string
  index: number
}

/** 结果分组：搜索态单组「搜索结果」；空搜索为「收藏」+「最近访问」 */
interface SearchGroup {
  title: string
  entries: SearchEntry[]
}

const menuStore = useMenuStore()
const { pushSafe } = useRouterSafe()
const { favorites, isFavorite, toggleFavorite } = useMenuFavorites()
const { recentMenus, recordMenu } = useRecentMenus()

const keyword = ref('')
const activeIndex = ref(0)

/** label / key / path 大小写不敏感子串匹配 */
function matchEntry(entry: FlatMenuEntry, query: string): boolean {
  return (
    entry.label.toLowerCase().includes(query) ||
    entry.key.toLowerCase().includes(query) ||
    entry.path.toLowerCase().includes(query)
  )
}

/** 过滤出当前用户仍可访问的存储记录（菜单删除/权限收回后自动隐藏） */
function accessibleRecords(records: NavMenuRecord[]): NavMenuRecord[] {
  return records.filter((record) => menuStore.canAccessMenu(record.key))
}

const groups = computed<SearchGroup[]>(() => {
  const query = keyword.value.trim().toLowerCase()
  let grouped: Array<{ title: string; records: Array<FlatMenuEntry | NavMenuRecord> }>
  if (query) {
    grouped = [
      {
        title: '搜索结果',
        records: menuStore.flatEntries.filter((entry) => matchEntry(entry, query)),
      },
    ]
  } else {
    const favoriteRecords = accessibleRecords(favorites.value)
    const favoriteKeys = new Set(favoriteRecords.map((record) => record.key))
    const recentRecords = accessibleRecords(recentMenus.value).filter(
      (record) => !favoriteKeys.has(record.key)
    )
    grouped = [
      { title: '收藏', records: favoriteRecords },
      { title: '最近访问', records: recentRecords },
    ]
  }

  let index = 0
  const result: SearchGroup[] = []
  for (const group of grouped) {
    if (group.records.length === 0) continue
    result.push({
      title: group.title,
      entries: group.records.map((record) => {
        const entry: SearchEntry = {
          key: record.key,
          label: record.label,
          path: record.path,
          icon: record.icon,
          sectionLabel: 'sectionLabel' in record ? record.sectionLabel : undefined,
          index,
        }
        index += 1
        return entry
      }),
    })
  }
  return result
})

/** 键盘上下键的可选条目（展平分组） */
const selectableEntries = computed(() => groups.value.flatMap((group) => group.entries))

/** 空态提示语：无历史 vs 无搜索结果 */
const emptyHint = computed(() => (keyword.value.trim() ? '未找到匹配的菜单' : '暂无收藏与最近访问'))

/** 选中并跳转：记录最近访问、关闭弹窗、安全跳转 */
function choose(entry: SearchEntry): void {
  recordMenu({ key: entry.key, label: entry.label, path: entry.path, icon: entry.icon })
  visible.value = false
  pushSafe(entry.path)
}

/** 键盘回车：跳转当前高亮项 */
function chooseActive(): void {
  const entry = selectableEntries.value[activeIndex.value]
  if (entry) choose(entry)
}

/** 上下移动高亮（循环） */
function moveActive(delta: number): void {
  const total = selectableEntries.value.length
  if (total === 0) return
  activeIndex.value = (activeIndex.value + delta + total) % total
}

/** 收藏切换（行内星标，阻止冒泡避免触发跳转） */
function toggleFavoriteEntry(entry: SearchEntry): void {
  toggleFavorite({ key: entry.key, label: entry.label, path: entry.path, icon: entry.icon })
}

/** 全局键盘监听：仅弹窗打开时生效 */
function onWindowKeydown(event: KeyboardEvent): void {
  if (!visible.value) return
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    moveActive(1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    moveActive(-1)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    chooseActive()
  } else if (event.key === 'Escape') {
    event.preventDefault()
    visible.value = false
  }
}

watch(visible, (isOpen: boolean) => {
  if (isOpen) {
    keyword.value = ''
    activeIndex.value = 0
  }
})

// 关键词变化后重置高亮，避免指向已过滤掉的条目
watch(keyword, () => {
  activeIndex.value = 0
})

onMounted(() => window.addEventListener('keydown', onWindowKeydown))
onUnmounted(() => window.removeEventListener('keydown', onWindowKeydown))
</script>

<style scoped>
.menu-search {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm, 8px);
  min-height: 200px;
}

.menu-search-input {
  width: 100%;
}

.menu-search-list {
  max-height: 420px;
  overflow-y: auto;
  padding: 4px 0;
}

.menu-search-group + .menu-search-group {
  margin-top: 8px;
}

.menu-search-group-title {
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-secondary);
  letter-spacing: 0.04em;
}

.menu-search-item {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  padding: 9px 10px;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-primary);
  font-size: 14px;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.18s ease;
}

.menu-search-item:hover,
.menu-search-item.is-active {
  background: var(--color-bg-hover);
}

.menu-search-item-icon {
  flex-shrink: 0;
  color: var(--color-primary);
}

.menu-search-item-label {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.menu-search-item-section {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--color-text-placeholder);
}

.menu-search-item-star {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  padding: 2px;
  border-radius: 4px;
  color: var(--color-text-placeholder);
  transition: color 0.18s ease;
}

.menu-search-item-star:hover,
.menu-search-item-star.is-starred {
  color: var(--color-warning);
}
</style>
