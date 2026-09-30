import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { useUploadHeaders } from '@/composables/useUploadHeaders'

vi.mock('@/api/request', () => ({
  getCsrfToken: vi.fn(() => Promise.resolve('mock-csrf')),
}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { getToken: vi.fn(() => 'mock-token') },
}))

const logMocks = vi.hoisted(() => ({ error: vi.fn(), warn: vi.fn(), info: vi.fn(), debug: vi.fn() }))
vi.mock('@/utils/logger', () => ({ logger: logMocks }))

import { getCsrfToken } from '@/api/request'
import { AuthStorage } from '@/utils/authStorage'

function mountHost() {
  let api: any
  const Comp = defineComponent({
    setup() {
      api = useUploadHeaders()
      return () => h('div')
    },
  })
  const w = mount(Comp, { attachTo: document.body })
  return { w, getApi: () => api }
}

describe('useUploadHeaders（el-upload CSRF 修复）', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })
  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('挂载后预取 CSRF 并携带 Authorization + X-CSRF-Token', async () => {
    const { w, getApi } = mountHost()
    await vi.waitFor(() => expect(getCsrfToken).toHaveBeenCalled())
    const api = getApi()
    expect(api.uploadHeaders.value).toMatchObject({
      Authorization: 'Bearer mock-token',
      'X-CSRF-Token': 'mock-csrf',
    })
    w.unmount()
  })

  it('无 token 时仅携带 X-CSRF-Token', async () => {
    ;(AuthStorage.getToken as any).mockReturnValue('')
    const { w, getApi } = mountHost()
    await vi.waitFor(() => expect(getCsrfToken).toHaveBeenCalled())
    const api = getApi()
    expect(api.uploadHeaders.value['X-CSRF-Token']).toBe('mock-csrf')
    expect(api.uploadHeaders.value.Authorization).toBeUndefined()
    w.unmount()
  })

  it('ensureCsrf 可手动重新触发', async () => {
    const { w, getApi } = mountHost()
    const api = getApi()
    ;(getCsrfToken as any).mockClear()
    api.ensureCsrf()
    await vi.waitFor(() => expect(getCsrfToken).toHaveBeenCalled())
    w.unmount()
  })

  // ── 2026-09-30 深审修复新增用例 ──

  it('ensureCsrf 返回 Promise：await 返回后 token 必已就绪（原实现不 return，await 立即 resolve）', async () => {
    const { w, getApi } = mountHost()
    const api = getApi()
    let resolveToken: (v: string) => void = () => {}
    ;(getCsrfToken as any).mockReturnValueOnce(
      new Promise<string>((resolve) => {
        resolveToken = resolve
      })
    )
    const pending = api.ensureCsrf()
    expect(pending).toBeInstanceOf(Promise)
    // 未 resolve 前不得提前完成（原实现此处已 resolve，token 尚为空）
    let settled = false
    void pending.then(() => {
      settled = true
    })
    await Promise.resolve()
    expect(settled).toBe(false)

    resolveToken('late-csrf')
    await pending
    expect(api.uploadHeaders.value['X-CSRF-Token']).toBe('late-csrf')
    w.unmount()
  })

  it('getCsrfToken 返回空串 → 不写入 X-CSRF-Token', async () => {
    ;(getCsrfToken as any).mockResolvedValue('')
    try {
      const { w, getApi } = mountHost()
      const api = getApi()
      await api.ensureCsrf()
      expect(api.uploadHeaders.value['X-CSRF-Token']).toBeUndefined()
      w.unmount()
    } finally {
      ;(getCsrfToken as any).mockResolvedValue('mock-csrf') // 恢复工厂默认实现
    }
  })

  it('getCsrfToken 失败 → 记录 warn 且 ensureCsrf 不抛出', async () => {
    const { w, getApi } = mountHost()
    const api = getApi()
    ;(getCsrfToken as any).mockRejectedValueOnce(new Error('csrf down'))
    await expect(api.ensureCsrf()).resolves.toBeUndefined()
    expect(logMocks.warn).toHaveBeenCalledWith('[useUploadHeaders] CSRF token 预取失败:', expect.any(Error))
    w.unmount()
  })
})
