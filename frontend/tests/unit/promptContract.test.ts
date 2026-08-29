/**
 * 提示层契约测试（"登录已过期看不清"修复回归防护）
 * - messageDefaults：grouping 去重 + showClose + 5s 时长
 * - EP 官方 message 样式已显式注入（main.ts import，构建产物核验由 CI 承担）
 * - 401 四分支统一走 _handleSessionExpired（文案/去重/延迟跳转见 request.test.ts）
 */
import { describe, it, expect, vi } from 'vitest'

const messageDefaultsState = { showClose: false, duration: 3000, grouping: false }

vi.mock('element-plus', async (importOriginal) => {
  const actual: any = await importOriginal()
  return {
    ...actual,
    messageDefaults: messageDefaultsState,
  }
})

describe('提示层契约（main.ts 全局默认）', () => {
  it('messageDefaults 开启 grouping 去重、showClose、5s 时长', async () => {
    await import('@/main')
    expect(messageDefaultsState.grouping).toBe(true)
    expect(messageDefaultsState.showClose).toBe(true)
    expect(messageDefaultsState.duration).toBe(5000)
  })

  it('constants.ts SYSTEM_VERSION 读取 VITE_APP_VERSION 并有兜底', async () => {
    const mod = await import('@/config/constants')
    expect(mod.SYSTEM_VERSION).toMatch(/^\d+\.\d+\.\d+/)
    expect(typeof mod.COPYRIGHT_OWNER).toBe('string')
    expect(mod.SYSTEM_NAME.length).toBeGreaterThan(0)
  })
})
