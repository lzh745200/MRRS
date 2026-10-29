/**
 * T037：锁屏归来消息摘要
 * 锁定瞬间打点（markLockNow）；登录/解锁恢复后首次未读轮询时消费（consumeLockDigest）。
 */
import { safeGetItem, safeSetItem, safeRemoveItem } from '@/utils/safeStorage'

const KEY = 'lock-digest-last-ts'
const WINDOW_MS = 30 * 60 * 1000 // 仅近 30 分钟内锁定过的才弹摘要

export function markLockNow(now = Date.now()): void {
  safeSetItem(KEY, String(now), 'local')
}

export function consumeLockDigest(unread: number, now = Date.now()): boolean {
  const raw = safeGetItem(KEY, 'local')
  const last = raw ? Number(raw) : 0
  // 删除失败 = 打点没清掉，下次还会弹 → 本次放弃，避免重复摘要
  if (!safeRemoveItem(KEY, 'local')) return false
  if (!last) return false
  if (now - last > WINDOW_MS) return false
  return unread > 0
}
