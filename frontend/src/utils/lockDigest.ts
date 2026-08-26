# -*- coding: utf-8 -*-
"""T037：锁屏归来消息摘要判定（纯函数，供 DefaultLayoutSafe 轮询处调用）。"""

const KEY = "lock-digest-last-ts"
const WINDOW_MS = 30 * 60 * 1000 // 仅近 30 分钟内锁定过的才弹摘要

export function markLockNow(now = Date.now()): void {
  try {
    localStorage.setItem(KEY, String(now))
  } catch {
    /* storage 不可用静默 */
  }
}

export function consumeLockDigest(unread: number, now = Date.now()): boolean {
  let last = 0
  try {
    const raw = localStorage.getItem(KEY)
    last = raw ? Number(raw) : 0
    localStorage.removeItem(KEY)
  } catch {
    return false
  }
  if (!last) return false
  if (now - last > WINDOW_MS) return false
  return unread > 0
}
