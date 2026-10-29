/**
 * 安全 Storage 访问（2026-10-29 全库审计）。
 *
 * 为什么需要：浏览器在**隐私模式 / 禁用 Cookie / 受限 webview** 下访问
 * localStorage / sessionStorage 会抛 SecurityError。以下调用点都在关键路径上：
 *
 * - `router/guards.ts` 每次导航调 `AuthStorage.getToken()`
 * - `composables/useAutoLock` 在 setup 期间读
 * - `composables/useVersionCheck` 在启动检查里读
 *
 * 一抛就是整次跳转/整页挂掉，且这类环境在现场终端不罕见。
 * 约定：**读取异常返回 fallback（fail-closed，视作"没有"）**，写入异常静默丢弃
 * （内存态仍可用，不阻断业务）。
 */

type StorageKind = 'local' | 'session'

function pick(kind: StorageKind): Storage {
  return kind === 'local' ? window.localStorage : window.sessionStorage
}

/** 读；任何异常（含 window 不存在）都返回 fallback */
export function safeGetItem(key: string, kind: StorageKind = 'local'): string | null {
  try {
    return pick(kind).getItem(key)
  } catch {
    return null
  }
}

/** 写；配额满/禁用时静默丢弃（不阻断业务） */
export function safeSetItem(key: string, value: string, kind: StorageKind = 'local'): boolean {
  try {
    pick(kind).setItem(key, value)
    return true
  } catch {
    return false
  }
}

/** 删；异常静默 */
export function safeRemoveItem(key: string, kind: StorageKind = 'local'): void {
  try {
    pick(kind).removeItem(key)
  } catch {
    /* ignore */
  }
}

/** 是否可用（个别场景需要区分"没有值"与"存储不可用"） */
export function isStorageAvailable(kind: StorageKind = 'local'): boolean {
  try {
    const s = pick(kind)
    const probe = '__storage_probe__'
    s.setItem(probe, '1')
    s.removeItem(probe)
    return true
  } catch {
    return false
  }
}
