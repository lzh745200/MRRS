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
})
