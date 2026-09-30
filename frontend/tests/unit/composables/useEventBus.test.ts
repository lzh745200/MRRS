import { describe, it, expect, beforeEach, vi } from 'vitest'

// 2026-09-30 深审修复：emit 逐个 handler 隔离异常并 logger.error 上报
const logMocks = vi.hoisted(() => ({ error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() }))
vi.mock('@/utils/logger', () => ({ logger: logMocks }))

import { getEventBus, useEventBus } from '@/composables/useEventBus'

describe('eventBus', () => {
  beforeEach(() => {
    // clear() 为新增 API：单例 Map 在用例间保持隔离
    getEventBus().clear()
    logMocks.error.mockClear()
  })

  it('useEventBus 返回 bus with on/off/emit', () => {
    const bus = useEventBus()
    expect(typeof bus.on).toBe('function')
    expect(typeof bus.off).toBe('function')
    expect(typeof bus.emit).toBe('function')
  })

  it('getEventBus 返回新实例但共享 state', () => {
    const a = getEventBus()
    const b = getEventBus()
    expect(a).not.toBe(b) // 不同实例
    const handler = () => {}
    a.on('shared', handler)
    b.emit('shared')
    // 共享 eventHandlers
  })

  it('on 注册 + emit 触发 handler', () => {
    const bus = useEventBus()
    const handler = vi.fn()
    bus.on('test-event', handler)
    bus.emit('test-event', 1, 2, 3)
    expect(handler).toHaveBeenCalledWith(1, 2, 3)
  })

  it('off 注销 handler', () => {
    const bus = useEventBus()
    const handler = vi.fn()
    bus.on('off-event', handler)
    bus.off('off-event', handler)
    bus.emit('off-event', 'x')
    expect(handler).not.toHaveBeenCalled()
  })

  it('off 不存在的 handler 不报错', () => {
    const bus = useEventBus()
    expect(() => bus.off('nonexistent', () => {})).not.toThrow()
  })

  it('emit 多个 handler 都触发', () => {
    const bus = useEventBus()
    const h1 = vi.fn()
    const h2 = vi.fn()
    bus.on('multi', h1)
    bus.on('multi', h2)
    bus.emit('multi', 'data')
    expect(h1).toHaveBeenCalledWith('data')
    expect(h2).toHaveBeenCalledWith('data')
  })

  it('emit 无订阅者不报错', () => {
    const bus = useEventBus()
    expect(() => bus.emit('no-subs', 'x')).not.toThrow()
  })

  it('on 同 handler 多次注册只触发一次 (Set 行为)', () => {
    const bus = useEventBus()
    const handler = vi.fn()
    bus.on('dedup', handler)
    bus.on('dedup', handler)
    bus.emit('dedup')
    expect(handler).toHaveBeenCalledTimes(1)
  })

  // ── 2026-09-30 深审修复新增用例 ──

  it('emit：单个 handler 抛错被隔离，其余 handler 仍执行且记录错误', () => {
    const bus = useEventBus()
    const boom = vi.fn(() => {
      throw new Error('handler failed')
    })
    const after = vi.fn()
    bus.on('isolate', boom)
    bus.on('isolate', after)

    expect(() => bus.emit('isolate', 'arg')).not.toThrow()
    expect(boom).toHaveBeenCalledWith('arg')
    // 原实现用 Map.forEach，抛错会中断迭代 → after 被静默跳过
    expect(after).toHaveBeenCalledWith('arg')
    expect(logMocks.error).toHaveBeenCalledWith(
      '[eventBus] 事件 "isolate" 的处理器执行失败:',
      expect.any(Error)
    )
  })

  it('emit：handler 内部 off 自身不影响本次派发的其余订阅者（快照迭代）', () => {
    const bus = useEventBus()
    const first = vi.fn(() => bus.off('snapshot', first))
    const second = vi.fn()
    bus.on('snapshot', first)
    bus.on('snapshot', second)
    bus.emit('snapshot')
    expect(first).toHaveBeenCalledTimes(1)
    expect(second).toHaveBeenCalledTimes(1)
    bus.emit('snapshot')
    expect(second).toHaveBeenCalledTimes(2)
  })

  it('clear(event) 只清指定事件；clear() 清空全部订阅', () => {
    const bus = useEventBus()
    const a = vi.fn()
    const b = vi.fn()
    bus.on('e1', a)
    bus.on('e2', b)

    bus.clear('e1')
    bus.emit('e1')
    bus.emit('e2')
    expect(a).not.toHaveBeenCalled()
    expect(b).toHaveBeenCalledTimes(1)

    bus.clear()
    bus.emit('e2')
    expect(b).toHaveBeenCalledTimes(1)
  })
})
