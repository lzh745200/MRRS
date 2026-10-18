/**
 * 列表筛选状态记忆（sessionStorage，按路由 key 隔离）。
 *
 * 背景：村 / 项目 / 经费列表刷新或跳转回来后筛选条件全部回到默认值，
 * 用户需要重复输入。这里把筛选对象按「路由 path」写入 sessionStorage
 * （会话级、关浏览器即失效，避免跨用户/跨会话串数据），进入列表时恢复。
 *
 * 安全与健壮性约定：
 * - key 一律带 `filter_memory:` 前缀 + 路由 path，不同列表互不覆盖；
 * - load 对「JSON 解析失败 / 非对象 / null / 数组」全部兜底为 null，
 *   并顺手清除脏数据，绝不把异常抛给页面；
 * - getItem / setItem / removeItem 任一步失败（隐私模式、配额满）都静默降级；
 * - apply 只回填目标对象**自身已有**的字段，避免被 JSON 里的额外键
 *   （如 `__proto__`）污染筛选对象原型。
 */
import { useRoute } from 'vue-router'

/** sessionStorage key 前缀 */
export const FILTER_MEMORY_PREFIX = 'filter_memory:'

/** useFilterMemory 选项 */
export interface FilterMemoryOptions {
  /** 显式指定记忆 key（默认取当前路由 path；两者都会拼接 FILTER_MEMORY_PREFIX） */
  key?: string
  /** 存储介质（默认 sessionStorage，测试可注入） */
  storage?: Storage
}

/** 筛选记忆实例 */
export interface FilterMemory<T extends Record<string, any>> {
  /** 最终使用的存储 key（含前缀），便于调试/断言 */
  readonly key: string
  /** 读取已保存的筛选（无记录 / 数据损坏 → null） */
  load(): Partial<T> | null
  /** 保存筛选（写失败静默） */
  save(filters: T): void
  /** 清除已保存的筛选 */
  clear(): void
  /** 把已保存的筛选回填到目标对象（只回填目标已有字段）；有回填返回 true */
  apply(target: T): boolean
}

/** 生成存储 key：`filter_memory:<路由 path>`，无路由信息时回落 unknown */
export function buildFilterMemoryKey(routePath?: string | null): string {
  return `${FILTER_MEMORY_PREFIX}${routePath || 'unknown'}`
}

export function useFilterMemory<T extends Record<string, any> = Record<string, any>>(
  options: FilterMemoryOptions = {}
): FilterMemory<T> {
  // 显式传 key 时不依赖路由上下文（也可在组件 setup 之外的单测中使用）
  const route = options.key === undefined ? useRoute() : null
  const key = buildFilterMemoryKey(options.key ?? route?.path)
  const storage = options.storage ?? sessionStorage

  function removeQuietly(): void {
    try {
      storage.removeItem(key)
    } catch {
      /* 存储不可用（隐私模式等）→ 静默降级 */
    }
  }

  function load(): Partial<T> | null {
    let raw: string | null
    try {
      raw = storage.getItem(key)
    } catch {
      return null
    }
    if (!raw) return null
    try {
      const parsed: unknown = JSON.parse(raw)
      if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        // 历史脏数据（null / 数组 / 标量）清掉，避免每次进入列表都重复解析
        removeQuietly()
        return null
      }
      return parsed as Partial<T>
    } catch {
      // JSON 解析失败兜底：清除损坏记录并视为「无记忆」
      removeQuietly()
      return null
    }
  }

  function save(filters: T): void {
    try {
      storage.setItem(key, JSON.stringify(filters))
    } catch {
      /* 配额满 / 循环引用 / 存储不可用 → 静默降级，不影响列表主流程 */
    }
  }

  function clear(): void {
    removeQuietly()
  }

  function apply(target: T): boolean {
    const saved = load()
    if (!saved) return false
    let applied = false
    for (const field of Object.keys(target)) {
      if (Object.prototype.hasOwnProperty.call(saved, field)) {
        ;(target as Record<string, any>)[field] = (saved as Record<string, any>)[field]
        applied = true
      }
    }
    return applied
  }

  return { key, load, save, clear, apply }
}
