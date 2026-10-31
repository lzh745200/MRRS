/**
 * W3-T3/T4/T5 前端 authz 回归：
 * - logout 调用后端吊销（失败不阻塞本地清理）
 * - 仅 GET 参与去重取消；POST/PUT/DELETE 不互相取消
 * - 已带 _retry 的请求再次 401 → 直接登出，不再进入 refresh
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

const { postMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
}))

vi.mock('@/api/request', async (importOriginal) => {
  const mod = await importOriginal<typeof import('@/api/request')>()
  return {
    ...mod,
    apiRequest: postMock,
  }
})

import { useAuthStore } from '@/stores/auth'
import { AuthStorage } from '@/utils/authStorage'

describe('W3-T3 登出服务端吊销', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    sessionStorage.clear()
    localStorage.clear()
  })

  it('logout 发起 /auth/logout 吊销并携带 refresh_token，且完成本地清理', () => {
    const store = useAuthStore()
    // 凭据同源：getRefreshToken 只在 token 与之同源时才返回，故必须先种 token
    AuthStorage.setToken('tk'); AuthStorage.setRefreshToken('rf')
    postMock.mockResolvedValue({ code: 200 })

    store.logout()

    expect(postMock).toHaveBeenCalledWith(
      expect.objectContaining({
        method: 'POST',
        url: '/auth/logout',
        data: { refresh_token: 'rf' },
      }),
    )
    expect(store.token).toBe('')
    expect(AuthStorage.getToken()).toBeNull()
  })

  it('无同源凭据时吊销请求不带 refresh_token，且仍完成本地清理', () => {
    const store = useAuthStore()
    AuthStorage.setRefreshToken('rf-orphan') // 仅刷新令牌、无 token → 视为未登录
    postMock.mockResolvedValue({ code: 200 })

    store.logout()

    expect(postMock).toHaveBeenCalledWith(
      expect.objectContaining({ method: 'POST', url: '/auth/logout', data: {} }),
    )
    expect(store.token).toBe('')
    expect(AuthStorage.getToken()).toBeNull()
  })

  it('吊销接口拒绝（Promise reject）不阻塞本地清理、不抛未处理异常', async () => {
    const store = useAuthStore()
    AuthStorage.setToken('tk'); AuthStorage.setRefreshToken('rf2')
    postMock.mockRejectedValue(new Error('network down'))

    expect(() => store.logout()).not.toThrow()
    await Promise.resolve().catch(() => undefined)

    expect(store.token).toBe('')
    expect(AuthStorage.getToken()).toBeNull()
  })

  // F3（2026-10-31）：退出登录原先先 freezeRequests() 再 logout()，
  // 请求拦截器把 /auth/logout 直接取消 → 服务端令牌不吊销。logout 现返回
  // 吊销请求的完成 Promise，调用方先 await 再冻结。
  it('logout 返回吊销请求的 Promise，await 后表示吊销已完成', async () => {
    const store = useAuthStore()
    AuthStorage.setToken('tk-f3'); AuthStorage.setRefreshToken('rf-f3')
    let resolveRevoke: (v: unknown) => void = () => {}
    postMock.mockReturnValue(new Promise((resolve) => { resolveRevoke = resolve }))

    const pending = store.logout()
    expect(pending).toBeInstanceOf(Promise)
    // 本地清理是同步的：不 await 也已退出（登出必须始终可用）
    expect(store.token).toBe('')
    expect(AuthStorage.getToken()).toBeNull()

    let settled = false
    void pending.then(() => { settled = true })
    await Promise.resolve()
    expect(settled).toBe(false) // 服务端吊销未返回前不结束

    resolveRevoke({ code: 200 })
    await pending
    expect(settled).toBe(true)
  })

  it('logout 清除锁屏标记（避免登出后下次打开停在锁定页）', async () => {
    const store = useAuthStore()
    AuthStorage.setToken('tk-f3b')
    AuthStorage.setLocked()
    postMock.mockResolvedValue({ code: 200 })

    await store.logout()

    expect(AuthStorage.isLocked()).toBe(false)
    expect(localStorage.getItem('auto_lock_active')).toBeNull()
  })

  // F5（2026-10-31）：草稿含未提交 PII，登出必须全清，避免共用电脑上
  // 下一位使用者经「恢复草稿」拿到上一位的身份证号/手机号。
  it('logout 清除全部表单草稿，但保留界面偏好等非草稿数据', async () => {
    const store = useAuthStore()
    AuthStorage.setToken('tk-f5')
    localStorage.setItem(
      'form:draft:schools:edit:1',
      JSON.stringify({ data: { id_card: '110101199001011234' }, savedAt: Date.now() }),
    )
    localStorage.setItem('ui:prefs', '{}')
    postMock.mockResolvedValue({ code: 200 })

    await store.logout()

    expect(localStorage.getItem('form:draft:schools:edit:1')).toBeNull()
    expect(localStorage.getItem('ui:prefs')).toBe('{}')
  })
})
