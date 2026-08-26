/**
 * 自动锁屏 composable（改用依赖注入式实现,便于测试与 ESM 兼容）
 */
import { onMounted, onUnmounted } from 'vue'
import { markLockNow } from '@/utils/lockDigest'

const STORAGE_KEY = 'auto-lock-minutes'
const DEFAULT_MINUTES = 15

export interface AutoLockOptions {
  /** 分钟数读取函数（默认 localStorage） */
  getMinutes?: () => number
  /** 锁屏回调（默认清会话跳登录） */
  onLock?: () => void
  /** 重置计时器（测试注入） */
  now?: () => number
}

export function useAutoLock(opts: AutoLockOptions = {}) {
  let timer: number | null = null

  const getMinutes =
    opts.getMinutes ??
    (() => {
      const raw = Number(window.localStorage.getItem(STORAGE_KEY))
      return Number.isFinite(raw) && raw > 0 ? raw : DEFAULT_MINUTES
    })

  const lockNow =
    opts.onLock ??
    (() => {
      // 默认行为: 结束会话（保留"记住登录"持久凭据）+ 锁屏标记 + 跳登录页
      try {
        const { AuthStorage } = require('@/utils/authStorage')
        AuthStorage.clearSession()
        window.sessionStorage.setItem('auto_lock_active', '1')
        markLockNow()
      } catch {
        /* 静默 */
      }
    })

  const resetTimer = () => {
    if (timer !== null) {
      window.clearTimeout(timer)
    }
    timer = window.setTimeout(() => lockNow(), getMinutes() * 60 * 1000)
  }

  const handlers = ['mousemove', 'keydown', 'click', 'touchstart'] as const

  const bind = () => {
    handlers.forEach((h) => window.addEventListener(h, resetTimer))
    resetTimer()
  }

  const unbind = () => {
    handlers.forEach((h) => window.removeEventListener(h, resetTimer))
    if (timer !== null) {
      window.clearTimeout(timer)
      timer = null
    }
  }

  onMounted(bind)
  onUnmounted(unbind)

  return { getMinutes, lockNow, resetTimer, unbind }
}
