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
  // 优先用**全局** localStorage/sessionStorage：jsdom 里 window.localStorage 与
  // 全局对象不一定是同一个，测试用 vi.stubGlobal('localStorage', stub) 替换的是全局，
  // 走 window.* 会绕过桩、打到真实 jsdom Storage（实测会让"写入失败降级"的用例失效）。
  // 浏览器里两者等同；无 window 的环境（SSR/单测）回退到 window，再不行则抛错由上层 catch。
  const g = globalThis as unknown as Record<string, Storage | undefined>
  const direct = g[kind === 'local' ? 'localStorage' : 'sessionStorage']
  if (direct) return direct
  if (typeof window !== 'undefined') {
    return kind === 'local' ? window.localStorage : window.sessionStorage
  }
  throw new Error('storage unavailable')
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

/**
 * 删；返回是否真的删成功。
 *
 * 为什么返回 boolean：个别调用点（lockDigest.consumeLockDigest）的语义依赖
 * 「删除失败 = 本次消费失败」—— 删不掉就打点还在，下次会重复弹摘要，因此要提前放弃。
 * 只静默吞掉异常会让那边谎报成功（单测已抓到）。
 */
export function safeRemoveItem(key: string, kind: StorageKind = 'local'): boolean {
  try {
    pick(kind).removeItem(key)
    return true
  } catch {
    return false
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
