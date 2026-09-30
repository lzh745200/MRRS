/**
 * 事件总线 Composable
 *
 * 订阅者异常隔离 + 显式释放：
 * - emit 逐个 handler 捕获异常，单个订阅者抛错不会打断其余订阅者；
 * - clear(event?) 释放订阅（全部或单个事件），避免组件漏调 off 时
 *   回调被模块级 Map 永久引用（陈旧执行 + Map 无界增长）。
 */
import { logger } from '@/utils/logger'

type EventHandler = (...args: any[]) => void

const eventHandlers = new Map<string, Set<EventHandler>>()

export function getEventBus() {
  function on(event: string, handler: EventHandler) {
    if (!eventHandlers.has(event)) {
      eventHandlers.set(event, new Set())
    }
    eventHandlers.get(event)!.add(handler)
  }

  function off(event: string, handler: EventHandler) {
    eventHandlers.get(event)?.delete(handler)
  }

  function emit(event: string, ...args: any[]) {
    const handlers = eventHandlers.get(event)
    if (!handlers) return
    // 快照迭代：处理器内部 on/off 不得改变本次派发的订阅者集合
    for (const handler of Array.from(handlers)) {
      try {
        handler(...args)
      } catch (err) {
        // 逐个隔离：Map.forEach 语义下任一订阅者抛错会静默跳过其余订阅者
        logger.error(`[eventBus] 事件 "${event}" 的处理器执行失败:`, err)
      }
    }
  }

  /** 清空订阅：clear() 全部，clear(event) 仅该事件 */
  function clear(event?: string) {
    if (event === undefined) eventHandlers.clear()
    else eventHandlers.delete(event)
  }

  return { on, off, emit, clear }
}

export function useEventBus() {
  return getEventBus()
}
