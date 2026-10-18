/**
 * 最近访问菜单（localStorage 持久化，上限 8 条）
 *
 * - 存储键：`nav:recent`
 * - 结构：`[{ key, label, path, icon? }]`
 * - 损坏数据（非 JSON / 非数组 / 缺字段）一律回退为空，不阻断导航
 * - 模块级单例：侧栏、菜单搜索弹窗、移动端导航共享同一份响应式数据
 */
import { ref, type Ref } from 'vue'

/** 最近访问/收藏菜单的最小记录（只存导航必需字段，菜单结构变化时降级丢弃） */
export interface NavMenuRecord {
  key: string
  label: string
  path: string
  icon?: string
}

export const RECENT_MENUS_STORAGE_KEY = 'nav:recent'
export const RECENT_MENUS_LIMIT = 8

const recentMenus: Ref<NavMenuRecord[]> = ref([])
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

/** 从 localStorage 读取最近访问（任何异常/脏数据回退空数组） */
function readStored(): NavMenuRecord[] {
  try {
    const raw = localStorage.getItem(RECENT_MENUS_STORAGE_KEY)
    if (!raw) return []
    const parsed: unknown = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(isStoredRecord).slice(0, RECENT_MENUS_LIMIT)
  } catch {
    return []
  }
}

/** 写回 localStorage（配额/隐私模式下静默降级，内存态仍可用） */
function persist(records: NavMenuRecord[]): void {
  try {
    localStorage.setItem(RECENT_MENUS_STORAGE_KEY, JSON.stringify(records))
  } catch {
    /* 存储不可用时忽略 */
  }
}

/** 重置模块级状态（供测试隔离使用） */
export function resetRecentMenus(): void {
  recentMenus.value = []
  initialized = false
}

export function useRecentMenus() {
  if (!initialized) {
    recentMenus.value = readStored()
    initialized = true
  }

  /** 记录一次访问：去重后置顶，超过上限截断 */
  function recordMenu(entry: NavMenuRecord): void {
    const next = [
      { key: entry.key, label: entry.label, path: entry.path, icon: entry.icon },
      ...recentMenus.value.filter((item) => item.key !== entry.key),
    ].slice(0, RECENT_MENUS_LIMIT)
    recentMenus.value = next
    persist(next)
  }

  /** 清空最近访问 */
  function clearRecentMenus(): void {
    recentMenus.value = []
    persist([])
  }

  return { recentMenus, recordMenu, clearRecentMenus }
}
