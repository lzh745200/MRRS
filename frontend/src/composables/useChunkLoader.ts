/**
 * useChunkLoader — Vite 动态 import 指数退避重试
 *
 * 包装 Vite 的动态 import()，在失败时自动重试（指数退避），
 * 防止因临时网络抖动或 CDN 故障导致单个 chunk 加载失败 → 全局白屏。
 *
 * Usage:
 *   // 在路由配置中替换原始 import()
 *   component: () => retryImport(() => import('@/views/Workbench.vue'))
 *
 *   重试策略（指数退避）:
 *     第1次失败 → 等待 baseDelay * 1 → 重试
 *     第2次失败 → 等待 baseDelay * 2 → 重试
 *     第3次失败 → 抛出错误
 */

/** 等待指定毫秒 */
function _wait(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

/**
 * 带指数退避重试的动态 import 包装器
 *
 * @param importFn  - Vite 动态 import 函数，如 () => import('./Foo.vue')
 * @param maxRetries - 最大重试次数（默认 3，总计最多 4 次尝试）
 * @param baseDelay  - 基础延迟毫秒数（默认 1000ms，实际延迟 = baseDelay × 重试序号）
 * @returns Promise<T> — 成功时返回模块，全部失败时抛出最后一次错误
 */
import { logger } from '@/utils/logger'

export async function retryImport<T = any>(
  importFn: () => Promise<T>,
  maxRetries: number = 3,
  baseDelay: number = 1000
): Promise<T> {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      return await importFn()
    } catch (error) {
      // 最后一次尝试失败 → 不再重试，向上抛出
      if (attempt >= maxRetries) {
        throw error
      }
      // 指数退避: attempt=0 → delay=baseDelay*1, attempt=1 → delay=baseDelay*2
      const delay = baseDelay * (attempt + 1)
      logger.warn(
        `[ChunkLoader] 模块加载失败，${delay}ms 后重试 (${attempt + 1}/${maxRetries})`,
        error instanceof Error ? error.message : error
      )
      await _wait(delay)
    }
  }
  // TypeScript 需要显式 throw（实际不会到达这里）
  throw new Error('[ChunkLoader] unreachable')
}

export default retryImport
