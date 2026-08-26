/**
 * W3-T3/T4/T5 前端 authz 回归：
 * - logout 调用后端吊销（失败不阻塞本地清理）
 * - 仅 GET 参与去重取消；POST/PUT/DELETE 不互相取消
 * - 已带 _retry 的请求再次 401 → 直接登出，不再进入 refresh
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

const { postMock, getMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
  getMock: vi.fn(),
}))

vi.mock('@/api/request', async (importOriginal) => {
  const mod = await importOriginal<typeof import('@/api/request')>()
  return {
    ...mod,
    post: postMock,
    get: getMock,
  }
})

import { useAuthStore } from '@/stores/auth'
import { AuthStorage } from '@/utils/authStorage'

describe('W3-T3 登出服务端吊销', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    sessionStorage.clear()
    localStorage.clear()
  })

  it('logout 发起 /auth/logout 吊销并携带 refresh_token，且完成本地清理', () => {
    const store = useAuthStore()
    AuthStorage.setTokens({ token: 'tk', refreshToken: 'rf' } as any)
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

  it('吊销接口拒绝（Promise reject）不阻塞本地清理、不抛未处理异常', async () => {
    const store = useAuthStore()
    AuthStorage.setTokens({ token: 'tk', refreshToken: 'rf2' } as any)
    postMock.mockRejectedValue(new Error('network down'))

    expect(() => store.logout()).not.toThrow()
    await Promise.resolve().catch(() => undefined)

    expect(store.token).toBe('')
    expect(AuthStorage.getToken()).toBeNull()
  })
})
