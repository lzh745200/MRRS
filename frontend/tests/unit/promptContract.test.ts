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

// main.ts 会挂载真实 App 并启动真实 router；jsdom 下初始导航会解析 /login 路由、
// 真实加载并执行 LoginEnhanced.vue 模块（WSL/Node22 全量实测 LE 模块恰好被两处加载：
// 本文件与专属测试 LoginEnhanced.test.ts）。覆盖率合并不变量要求该 .vue 全仓只被
// LoginEnhanced.test.ts 一个文件触碰，否则其在满量按 id 合并时 functions 跌到 88.23%
// （Linux CI 红、Windows/Node25 绿——OS 间 v8 函数 id 顺序差异，不能作为放行依据）。
// 此处以桩替换：main.ts 的 messageDefaults/版本契约断言不受影响，懒加载本体不再执行。
vi.mock('@/views/auth/LoginEnhanced.vue', () => ({ default: { name: 'LoginEnhancedContractStub' } }))

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
