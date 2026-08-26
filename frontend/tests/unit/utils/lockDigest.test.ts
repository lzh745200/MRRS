import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { consumeLockDigest, markLockNow } from '@/utils/lockDigest'

describe('lockDigest (T037)', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('未打点时不弹（consume=false）', () => {
    expect(consumeLockDigest(5)).toBe(false)
  })

  it('近30分钟内锁定且有未读 → 弹一次并消费打点', () => {
    const now = 1_800_000_000_000
    markLockNow(now - 10 * 60 * 1000, now)
    vi.setSystemTime(now)
    expect(consumeLockDigest(3, now)).toBe(true)
    expect(consumeLockDigest(3, now)).toBe(false) // 已消费
  })

  it('超出30分钟窗口不弹', () => {
    const now = 1_800_000_000_000
    markLockNow(now - 45 * 60 * 1000, now)
    expect(consumeLockDigest(2, now)).toBe(false)
  })

  it('无未读不弹', () => {
    const now = 1_800_000_000_000
    markLockNow(now - 5 * 60 * 1000, now)
    expect(consumeLockDigest(0, now)).toBe(false)
  })
})
