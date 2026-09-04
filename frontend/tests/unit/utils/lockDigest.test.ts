import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { consumeLockDigest, markLockNow } from '@/utils/lockDigest'

describe('lockDigest (T037)', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
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

/**
 * storage 不可用路径（隐私模式 / 配额耗尽 / Electron 会话未就绪）。
 * 源码用 try/catch 静默兜底，这两条 catch 分支在 jsdom 下不会自然触发。
 *
 * 注意：不能用 `vi.spyOn(Storage.prototype, 'setItem')` 也不能
 * `vi.spyOn(localStorage, 'setItem')`——jsdom 的 Storage 是带
 * getter/setter/deleter 的 WebIDL Proxy，向其写入任意属性会被当成
 * 一个存储项（已实测：spy 安装后调用数为 0，真实 setItem 仍生效）。
 * 因此改用 vi.stubGlobal 整体替换 localStorage 为普通对象桩。
 *
 * 覆盖后验证契约：
 *   markLockNow 绝不把异常抛给调用方（锁屏流程不能因打点失败而中断）；
 *   consumeLockDigest 返回 false（读不到打点就当没锁过，宁可不弹摘要）。
 */
describe('lockDigest storage 不可用兜底', () => {
  const NOW = 1_800_000_000_000

  /** 构造一个可逐项控制抛错的 localStorage 桩并挂到全局 */
  function stubStorage(impl: {
    setItem?: (key: string, value: string) => void
    getItem?: (key: string) => string | null
    removeItem?: (key: string) => void
  }) {
    const fns = {
      setItem: vi.fn(impl.setItem ?? (() => undefined)),
      getItem: vi.fn(impl.getItem ?? (() => null)),
      removeItem: vi.fn(impl.removeItem ?? (() => undefined)),
    }
    vi.stubGlobal('localStorage', fns)
    return fns
  }

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
    localStorage.clear()
  })

  it('markLockNow：setItem 抛错时被静默吞掉，不外泄异常', () => {
    const { setItem } = stubStorage({
      setItem: () => {
        throw new Error('QuotaExceededError')
      },
    })
    expect(() => markLockNow(NOW)).not.toThrow()
    // 抛错前确实已尝试写入正确的 key/值
    expect(setItem).toHaveBeenCalledWith('lock-digest-last-ts', String(NOW))
  })

  it('consumeLockDigest：getItem 抛错 → false（读不到打点当没锁过）', () => {
    const { getItem } = stubStorage({
      getItem: () => {
        throw new Error('SecurityError: storage disabled')
      },
    })
    // unread=3 且在窗口内，若无 catch 本应返回 true——证明 catch 优先于窗口判定
    expect(consumeLockDigest(3, NOW)).toBe(false)
    expect(getItem).toHaveBeenCalledWith('lock-digest-last-ts')
  })

  it('consumeLockDigest：removeItem 抛错 → false，且不会重复弹摘要', () => {
    const { removeItem } = stubStorage({
      getItem: () => String(NOW),
      removeItem: () => {
        throw new Error('SecurityError: storage disabled')
      },
    })
    expect(consumeLockDigest(3, NOW)).toBe(false)
    expect(removeItem).toHaveBeenCalledWith('lock-digest-last-ts')
  })

  it('桩件仍可验证正常路径：打点在窗口内且有未读 → true', () => {
    // 回归护栏：stubGlobal 后模块确实读到的是桩，而不是遗留的真 localStorage
    const store = new Map<string, string>()
    const { setItem, getItem } = stubStorage({
      setItem: (k, v) => void store.set(k, v),
      getItem: (k) => store.get(k) ?? null,
      removeItem: (k) => void store.delete(k),
    })
    markLockNow(NOW)
    expect(setItem).toHaveBeenCalledOnce()
    expect(store.get('lock-digest-last-ts')).toBe(String(NOW))
    expect(consumeLockDigest(2, NOW)).toBe(true)
    expect(getItem).toHaveBeenCalled()
    // 已被 removeItem 消费
    expect(store.has('lock-digest-last-ts')).toBe(false)
    expect(consumeLockDigest(2, NOW)).toBe(false)
  })
})
