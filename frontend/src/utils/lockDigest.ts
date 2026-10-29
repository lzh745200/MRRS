/**
 * T037：锁屏归来消息摘要
 * 锁定瞬间打点（markLockNow）；登录/解锁恢复后首次未读轮询时消费（consumeLockDigest）。
 */
import { safeGetItem, safeSetItem, safeRemoveItem } from '@/utils/safeStorage'

const KEY = 'lock-digest-last-ts'
const WINDOW_MS = 30 * 60 * 1000 // 仅近 30 分钟内锁定过的才弹摘要

export function markLockNow(now = Date.now()): void {
  try {
    safeSetItem(KEY, String(now), 'local')
  } catch {
    /* storage 不可用静默 */
  }
}

export function consumeLockDigest(unread: number, now = Date.now()): boolean {
  let last = 0
  try {
    const raw = safeGetItem(KEY, 'local')
    last = raw ? Number(raw) : 0
    // 删除失败 = 打点没清掉，下次还会弹 → 本次放弃，避免重复摘要
    if (!safeRemoveItem(KEY, 'local')) return false
  } catch {
    return false
  }
  if (!last) return false
  if (now - last > WINDOW_MS) return false
  return unread > 0
}
