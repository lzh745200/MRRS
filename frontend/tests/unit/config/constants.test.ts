import { describe, it, expect, vi, afterEach } from 'vitest'
import { SYSTEM_VERSION, COPYRIGHT_OWNER, SYSTEM_NAME } from '@/config/constants'

describe('config/constants', () => {
  it('SYSTEM_VERSION is a semver string', () => expect(SYSTEM_VERSION).toMatch(/^\d+\.\d+\.\d+$/))
  it('COPYRIGHT_OWNER', () => expect(COPYRIGHT_OWNER).toBe('梁正辉'))
  it('SYSTEM_NAME', () => expect(SYSTEM_NAME).toBe('帮扶管理信息系统'))
})

/**
 * SYSTEM_VERSION 的环境变量优先级与字符串兜底。
 *
 * 本地 frontend/.env 固定了 VITE_APP_VERSION（该文件被 gitignore，CI 上不存在），
 * 因此顶部静态导入在本地永远走 `||` 左侧，兜底常量（环境文件缺失时的最后防线，
 * 由 scripts/sync_version.py 随发版同步）无法被静态用例触达。
 * 这里用 vi.stubEnv + vi.resetModules + 动态 import 重新求值模块，
 * 分别覆盖两侧；兜底值一旦与发版号脱节，此用例会先于 UI 报错。
 */
describe('config/constants SYSTEM_VERSION 来源优先级', () => {
  afterEach(() => {
    vi.unstubAllEnvs()
    // 恢复模块注册表，避免 stub 过的实例泄露到其他测试文件/用例
    vi.resetModules()
  })

  it('VITE_APP_VERSION 有值时优先使用环境注入值', async () => {
    vi.stubEnv('VITE_APP_VERSION', '9.9.9')
    vi.resetModules()
    const mod = await import('@/config/constants')
    expect(mod.SYSTEM_VERSION).toBe('9.9.9')
  })

  it('VITE_APP_VERSION 为空串时回落到硬编码兜底版本', async () => {
    vi.stubEnv('VITE_APP_VERSION', '')
    vi.resetModules()
    const mod = await import('@/config/constants')
    expect(mod.SYSTEM_VERSION).toBe('1.11.5')
  })

  it('VITE_APP_VERSION 完全缺失时同样回落兜底版本', async () => {
    vi.stubEnv('VITE_APP_VERSION', undefined)
    vi.resetModules()
    const mod = await import('@/config/constants')
    expect(mod.SYSTEM_VERSION).toBe('1.11.5')
    // 兜底分支不影响其他常量
    expect(mod.COPYRIGHT_OWNER).toBe('梁正辉')
    expect(mod.SYSTEM_NAME).toBe('帮扶管理信息系统')
  })

  it('静态导入值符合「环境注入优先、否则兜底」契约', async () => {
    // 不钉死具体版本号：VITE_APP_VERSION 的来源是 frontend/.env（gitignored，
    // 本地存在、CI 不存在），硬编码其值会让本用例只在本地通过、在 CI 必失败。
    // 改为断言契约本身 —— 有注入值则等于注入值，否则等于兜底常量。
    vi.stubEnv('VITE_APP_VERSION', '')
    vi.resetModules()
    const fallback = (await import('@/config/constants')).SYSTEM_VERSION
    vi.unstubAllEnvs()
    vi.resetModules()

    const injected = import.meta.env.VITE_APP_VERSION
    expect(SYSTEM_VERSION).toBe(injected || fallback)
    expect(SYSTEM_VERSION).toMatch(/^\d+\.\d+\.\d+$/)
  })
})
