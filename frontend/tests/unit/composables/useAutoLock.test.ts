import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'

// 2026-09-30 深审修复：默认 lockNow 的 catch 由"完全静默"改为 logger.error 可观测。
// 为覆盖失败分支（真实环境无注入时不会失败），此处 mock 会话清理并令其抛错。
const authMocks = vi.hoisted(() => ({ clearSession: vi.fn() }))
const lockMocks = vi.hoisted(() => ({ markLockNow: vi.fn() }))
const logMocks = vi.hoisted(() => ({ error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() }))
vi.mock('@/utils/authStorage', () => ({ AuthStorage: { clearSession: authMocks.clearSession } }))
vi.mock('@/utils/lockDigest', () => ({ markLockNow: lockMocks.markLockNow }))
vi.mock('@/utils/logger', () => ({ logger: logMocks }))

import { useAutoLock } from '@/composables/useAutoLock'

function mountHost(opts: any = {}) {
  let api: any
  const Comp = defineComponent({
    setup() {
      api = useAutoLock(opts)
      return () => h('div')
    },
  })
  const w = mount(Comp, { attachTo: document.body })
  return { w, getApi: () => api }
}

describe('useAutoLock（自动锁屏）', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    localStorage.clear()
  })
  afterEach(() => {
    vi.useRealTimers()
    document.body.innerHTML = ''
  })

  it('默认 15 分钟锁屏', () => {
    const onLock = vi.fn()
    const { w, getApi } = mountHost({ onLock })
    const api = getApi()
    expect(api.getMinutes()).toBe(15)
    vi.advanceTimersByTime(15 * 60 * 1000 + 100)
    expect(onLock).toHaveBeenCalledTimes(1)
    w.unmount()
  })

  it('自定义分钟数与 onLock', () => {
    const onLock = vi.fn()
    const { w, getApi } = mountHost({ getMinutes: () => 2, onLock })
    const api = getApi()
    expect(api.getMinutes()).toBe(2)
    vi.advanceTimersByTime(2 * 60 * 1000 + 100)
    expect(onLock).toHaveBeenCalledTimes(1)
    w.unmount()
  })

  it('用户操作重置计时器', () => {
    const onLock = vi.fn()
    const { w, getApi } = mountHost({ getMinutes: () => 2, onLock })
    const api = getApi()
    // 1 分钟后有操作 → 重置
    vi.advanceTimersByTime(60 * 1000)
    window.dispatchEvent(new Event('mousemove'))
    vi.advanceTimersByTime(60 * 1000 + 100)
    expect(onLock).not.toHaveBeenCalled()
    vi.advanceTimersByTime(2 * 60 * 1000)
    expect(onLock).toHaveBeenCalledTimes(1)
    w.unmount()
  })

  it('卸载时清理定时器', () => {
    const onLock = vi.fn()
    const { w, getApi } = mountHost({ getMinutes: () => 1, onLock })
    const api = getApi()
    api.unbind()
    vi.advanceTimersByTime(10 * 60 * 1000)
    expect(onLock).not.toHaveBeenCalled()
    w.unmount()
  })

  it('localStorage 配置读取', () => {
    localStorage.setItem('auto-lock-minutes', '30')
    const { w, getApi } = mountHost()
    expect(getApi().getMinutes()).toBe(30)
    w.unmount()
  })

  it('非法配置回退默认', () => {
    localStorage.setItem('auto-lock-minutes', 'abc')
    const { w, getApi } = mountHost()
    expect(getApi().getMinutes()).toBe(15)
    w.unmount()
  })

  it('配置 0/负数 回退默认', () => {
    localStorage.setItem('auto-lock-minutes', '0')
    let { w, getApi } = mountHost()
    expect(getApi().getMinutes()).toBe(15)
    w.unmount()
    localStorage.setItem('auto-lock-minutes', '-5')
    ;({ w, getApi } = mountHost())
    expect(getApi().getMinutes()).toBe(15)
    w.unmount()
  })

  it('click/keydown/touchstart 事件均重置计时器', () => {
    const onLock = vi.fn()
    const { w, getApi } = mountHost({ getMinutes: () => 1, onLock })
    const api = getApi()
    vi.advanceTimersByTime(50 * 1000)
    window.dispatchEvent(new Event('click'))
    window.dispatchEvent(new Event('keydown'))
    window.dispatchEvent(new Event('touchstart'))
    // 事件在 t=50s 重置计时器 → 下一次触发在 t=110s
    vi.advanceTimersByTime(59 * 1000 + 100)
    expect(onLock).not.toHaveBeenCalled()
    vi.advanceTimersByTime(60 * 1000)
    expect(onLock).toHaveBeenCalledTimes(1)
    w.unmount()
  })

  it('resetTimer 二次调用时清除旧定时器（timer 非空分支）', () => {
    const onLock = vi.fn()
    const { w, getApi } = mountHost({ getMinutes: () => 1, onLock })
    const api = getApi()
    const clearSpy = vi.spyOn(window, 'clearTimeout')
    api.resetTimer()
    expect(clearSpy).toHaveBeenCalledTimes(1)
    w.unmount()
  })

  it('默认 lockNow（未注入 onLock）：清会话 + 落锁屏标记 + 记锁屏时间', () => {
    const { w } = mountHost()
    vi.advanceTimersByTime(15 * 60 * 1000 + 100)
    expect(authMocks.clearSession).toHaveBeenCalled()
    expect(window.sessionStorage.getItem('auto_lock_active')).toBe('1')
    expect(lockMocks.markLockNow).toHaveBeenCalled()
    expect(logMocks.error).not.toHaveBeenCalled()
    w.unmount()
  })

  it('默认 lockNow 失败 → 记录 error（原为完全静默的 catch）', () => {
    authMocks.clearSession.mockImplementationOnce(() => {
      throw new Error('storage broken')
    })
    const { w } = mountHost()
    expect(() => vi.advanceTimersByTime(15 * 60 * 1000 + 100)).not.toThrow()
    expect(logMocks.error).toHaveBeenCalledWith(
      '[useAutoLock] 锁屏执行失败（会话未清理/锁屏标记未写入）:',
      expect.any(Error)
    )
    w.unmount()
  })

  it('unbind 幂等：二次调用不抛错', () => {
    const { w, getApi } = mountHost()
    const api = getApi()
    api.unbind()
    expect(() => api.unbind()).not.toThrow()
    w.unmount()
  })
})
