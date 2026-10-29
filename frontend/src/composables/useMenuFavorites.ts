/**
 * 菜单收藏（localStorage 持久化，上限 8 条）
 *
 * - 存储键：`nav:favorites`
 * - 结构：`[{ key, label, path, icon? }]`
 * - 损坏数据（非 JSON / 非数组 / 缺字段）一律回退为空，不阻断导航
 * - 模块级单例：侧栏收藏区与菜单搜索弹窗共享同一份响应式数据
 */
import { ref, type Ref } from 'vue'
import type { NavMenuRecord } from '@/composables/useRecentMenus'
import { safeGetItem, safeSetItem } from '@/utils/safeStorage'

export const MENU_FAVORITES_STORAGE_KEY = 'nav:favorites'
export const MENU_FAVORITES_LIMIT = 8

const favoriteMenus: Ref<NavMenuRecord[]> = ref([])
let initialized = false

/** 校验单条存储记录（损坏字段直接丢弃） */
function isStoredRecord(value: unknown): value is NavMenuRecord {
  if (typeof value !== 'object' || value === null) return false
  const record = value as Record<string, unknown>
  return (
    typeof record.key === 'string' &&
    typeof record.label === 'string' &&
    typeof record.path === 'string'
  )
}

/** 从 localStorage 读取收藏（任何异常/脏数据回退空数组） */
function readStored(): NavMenuRecord[] {
  try {
    const raw = safeGetItem(MENU_FAVORITES_STORAGE_KEY, 'local')
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(isStoredRecord).slice(0, MENU_FAVORITES_LIMIT)
  } catch {
    return []
  }
}

/** 写回 localStorage（配额/隐私模式下静默降级，内存态仍可用） */
function persist(records: NavMenuRecord[]): void {
  try {
    safeSetItem(MENU_FAVORITES_STORAGE_KEY, JSON.stringify(records), 'local')
  } catch {
    /* 存储不可用时忽略 */
  }
}

/** 重置模块级状态（供测试隔离使用） */
export function resetMenuFavorites(): void {
  favoriteMenus.value = []
  initialized = false
}

export function useMenuFavorites() {
  if (!initialized) {
    favoriteMenus.value = readStored()
    initialized = true
  }

  /** 是否已收藏 */
  function isFavorite(key: string): boolean {
    return favoriteMenus.value.some((item) => item.key === key)
  }

  /**
   * 切换收藏状态。
   * @returns 切换后是否处于收藏态（true=已收藏）
   */
  function toggleFavorite(entry: NavMenuRecord): boolean {
    const exists = isFavorite(entry.key)
    if (exists) {
      favoriteMenus.value = favoriteMenus.value.filter((item) => item.key !== entry.key)
    } else {
      favoriteMenus.value = [
        {
          key: entry.key,
          label: entry.label,
          path: entry.path,
          icon: entry.icon,
          tabKey: entry.tabKey,
        },
        ...favoriteMenus.value,
      ].slice(0, MENU_FAVORITES_LIMIT)
    }
    persist(favoriteMenus.value)
    return !exists
  }

  /** 移除收藏（不存在时无副作用） */
  function removeFavorite(key: string): void {
    favoriteMenus.value = favoriteMenus.value.filter((item) => item.key !== key)
    persist(favoriteMenus.value)
  }

  /** 清空收藏 */
  function clearFavorites(): void {
    favoriteMenus.value = []
    persist([])
  }

  return {
    favorites: favoriteMenus,
    isFavorite,
    toggleFavorite,
    removeFavorite,
    clearFavorites,
  }
}
