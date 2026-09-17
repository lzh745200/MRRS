import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

vi.mock('@/api/request', () => ({
  default: vi.fn(),
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  patch: vi.fn(),
  cancelRequest: vi.fn(),
  cancelAllRequests: vi.fn(),
  isRequestCancelled: vi.fn(),
  getPendingRequestCount: vi.fn(),
  createCancelableRequest: vi.fn(),
  requestWithTimeout: vi.fn(),
  isSuccess: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve("test-csrf"))}))

vi.mock('@/utils/authStorage', () => ({
  AuthStorage: { clear: vi.fn(), getToken: vi.fn(), setToken: vi.fn(), getUser: vi.fn(() => null) },
}))

import { get, post, put, del } from '@/api/request'
import { AuthStorage } from '@/utils/authStorage'
import { useUserStore } from '@/stores/user'

describe('stores/user', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  describe('initial state', () => {
    it('userList/currentUser/loading/error/total 初始值', () => {
      const s = useUserStore()
      expect(s.userList).toEqual([])
      expect(s.currentUser).toBeNull()
      expect(s.loading).toBe(false)
      expect(s.error).toBeNull()
      expect(s.total).toBe(0)
    })

    it('AuthStorage 中有用户时 currentUser 初始化恢复', () => {
      ;(AuthStorage.getUser as any).mockReturnValue({ id: 5, username: 'restored' })
      const s = useUserStore()
      expect(s.currentUser).toEqual({ id: 5, username: 'restored' })
    })
  })

  describe('fetchUsers', () => {
    it('成功: 填充 userList + total', async () => {
      ;(get as any).mockResolvedValue({ code: 200, data: { items: [{ id: 1, name: 'A' }, { id: 2, name: 'B' }], total: 2 } })
      const s = useUserStore()
      await s.fetchUsers()
      expect(s.userList).toHaveLength(2)
      expect(s.total).toBe(2)
    })

    it('裸格式 res.items 直接使用', async () => {
      ;(get as any).mockResolvedValue({ items: [{ id: 1, name: 'A' }], total: 9 })
      const s = useUserStore()
      await s.fetchUsers()
      expect(s.userList).toHaveLength(1)
      expect(s.total).toBe(9)
    })

    it('无 total 字段时用 items.length 兜底', async () => {
      ;(get as any).mockResolvedValue({ items: [{ id: 1 }, { id: 2 }] })
      const s = useUserStore()
      await s.fetchUsers()
      expect(s.total).toBe(2)
    })

    it('data 缺失: userList=[]', async () => {
      ;(get as any).mockResolvedValue({ code: 200, data: null })
      const s = useUserStore()
      await s.fetchUsers()
      expect(s.userList).toEqual([])
      expect(s.total).toBe(0)
    })

    it('code !== 200: userList 不变', async () => {
      ;(get as any).mockResolvedValue({ code: 500, message: 'err' })
      const s = useUserStore()
      await s.fetchUsers()
      expect(s.userList).toEqual([])
    })

    it('data.items 缺失: 用 ?? fallback', async () => {
      ;(get as any).mockResolvedValue({ code: 200, data: { total: 5 } })
      const s = useUserStore()
      await s.fetchUsers()
      expect(s.userList).toEqual([])
      expect(s.total).toBe(5)
    })

    it('失败: 设置 error + loading=false', async () => {
      ;(get as any).mockRejectedValue(new Error('net'))
      const s = useUserStore()
      await s.fetchUsers()
      expect(s.error).toBe('net')
      expect(s.loading).toBe(false)
    })

    it('失败有 response.data.message: 用它', async () => {
      ;(get as any).mockRejectedValue({ response: { data: { message: 'Forbidden' } } })
      const s = useUserStore()
      await s.fetchUsers()
      expect(s.error).toBe('Forbidden')
    })

    it('失败无任何信息: 用默认错误文案', async () => {
      ;(get as any).mockRejectedValue({})
      const s = useUserStore()
      await s.fetchUsers()
      expect(s.error).toBe('获取用户列表失败')
    })
  })

  describe('fetchUser', () => {
    it('成功: 设置 currentUser + 返回 data', async () => {
      ;(get as any).mockResolvedValue({ code: 200, data: { id: 7, name: 'X' } })
      const s = useUserStore()
      const r = await s.fetchUser(7)
      expect(s.currentUser).toEqual({ id: 7, name: 'X' })
      expect(r).toEqual({ id: 7, name: 'X' })
    })

    it('裸对象响应直接作为 user', async () => {
      ;(get as any).mockResolvedValue({ id: 9, username: 'bare' })
      const s = useUserStore()
      const r = await s.fetchUser(9)
      expect(s.currentUser).toEqual({ id: 9, username: 'bare' })
      expect(r).toEqual({ id: 9, username: 'bare' })
    })

    it('响应为空时不修改 currentUser', async () => {
      ;(get as any).mockResolvedValue(null)
      const s = useUserStore()
      s.currentUser = { id: 1 } as any
      await s.fetchUser(1)
      expect(s.currentUser).toEqual({ id: 1 })
    })

    it('失败: error + loading=false', async () => {
      ;(get as any).mockRejectedValue(new Error('boom'))
      const s = useUserStore()
      await s.fetchUser(1)
      expect(s.error).toBe('boom')
      expect(s.loading).toBe(false)
    })

    it('失败无任何信息: 用默认错误文案', async () => {
      ;(get as any).mockRejectedValue({})
      const s = useUserStore()
      await s.fetchUser(1)
      expect(s.error).toBe('获取用户详情失败')
    })

    it('失败有 response.data.message: 用它', async () => {
      ;(get as any).mockRejectedValue({ response: { data: { message: 'Not Found' } } })
      const s = useUserStore()
      await s.fetchUser(1)
      expect(s.error).toBe('Not Found')
    })
  })

  describe('createUser', () => {
    it('成功: unshift 到 userList + total++', async () => {
      ;(post as any).mockResolvedValue({ code: 200, data: { id: 99, name: 'New' } })
      const s = useUserStore()
      s.userList.push({ id: 1, name: 'old' } as any)
      s.total = 1
      const r = await s.createUser({ name: 'New' })
      expect(r.code).toBe(200)
      expect(s.userList[0]).toEqual({ id: 99, name: 'New' })
      expect(s.total).toBe(2)
    })

    it('code !== 200: 不修改 userList', async () => {
      ;(post as any).mockResolvedValue({ code: 400 })
      const s = useUserStore()
      await s.createUser({ name: 'X' })
      expect(s.userList).toEqual([])
    })
  })

  describe('updateUser', () => {
    it('成功: 更新 userList 中对应项 + currentUser (若 id 匹配)', async () => {
      ;(put as any).mockResolvedValue({ code: 200, data: { id: 1, name: 'updated' } })
      const s = useUserStore()
      s.userList.push({ id: 1, name: 'old' } as any)
      s.currentUser = { id: 1, name: 'old' } as any
      await s.updateUser(1, { name: 'updated' })
      expect(s.userList[0].name).toBe('updated')
      expect(s.currentUser?.name).toBe('updated')
    })

    it('userList 中无对应 id: 不更新列表但 currentUser 仍更新', async () => {
      ;(put as any).mockResolvedValue({ code: 200, data: { id: 99, name: 'X' } })
      const s = useUserStore()
      await s.updateUser(99, { name: 'X' })
      expect(s.userList).toEqual([])
    })

    it('code !== 200: 不更新任何状态', async () => {
      ;(put as any).mockResolvedValue({ code: 500 })
      const s = useUserStore()
      s.userList.push({ id: 1, name: 'old' } as any)
      s.currentUser = { id: 1, name: 'old' } as any
      await s.updateUser(1, { name: 'updated' })
      expect(s.userList[0].name).toBe('old')
      expect(s.currentUser?.name).toBe('old')
    })
  })

  describe('deleteUser', () => {
    it('成功: 从 userList 移除 + total-- + 清空 currentUser (若 id 匹配)', async () => {
      ;(del as any).mockResolvedValue({ code: 200 })
      const s = useUserStore()
      s.userList.push({ id: 5, name: 'gone' } as any, { id: 6, name: 'stay' } as any)
      s.total = 2
      s.currentUser = { id: 5, name: 'gone' } as any
      await s.deleteUser(5)
      expect(s.userList).toHaveLength(1)
      expect(s.userList[0].id).toBe(6)
      expect(s.total).toBe(1)
      expect(s.currentUser).toBeNull()
    })

    it('currentUser id 不匹配: 保持不变', async () => {
      ;(del as any).mockResolvedValue({ code: 200 })
      const s = useUserStore()
      s.currentUser = { id: 99, name: 'Z' } as any
      await s.deleteUser(1)
      expect(s.currentUser?.id).toBe(99)
    })

    it('code !== 200: 不删除', async () => {
      ;(del as any).mockResolvedValue({ code: 500 })
      const s = useUserStore()
      s.userList.push({ id: 1 } as any)
      await s.deleteUser(1)
      expect(s.userList).toHaveLength(1)
    })
  })

  describe('resetUserPassword / assignRole / logout / uploadAvatar', () => {
    it('resetUserPassword POST 正确路径 + body', async () => {
      ;(post as any).mockResolvedValue({ code: 200 })
      const s = useUserStore()
      await s.resetUserPassword(7, 'newPass')
      expect(post).toHaveBeenCalledWith('/users/7/admin-reset-password', { new_password: 'newPass' })
    })

    it('assignRole 走 /users/{id}/permissions（已统一到 /users 族）', async () => {
      ;(put as any).mockResolvedValue({ code: 200 })
      const s = useUserStore()
      await s.assignRole(7, 'admin')
      expect(put).toHaveBeenCalledWith('/users/7/permissions', { role: 'admin' })
    })

    it('logout 清 AuthStorage', async () => {
      const s = useUserStore()
      await s.logout()
      expect(AuthStorage.clear).toHaveBeenCalled()
    })

    it('getUserProfile 无 id 抛错', async () => {
      ;(get as any).mockResolvedValue({ code: 500 })
      const s = useUserStore()
      await expect(s.getUserProfile()).rejects.toThrow('无法获取用户信息')
    })

    it('getUserProfile 用 currentUser.id', async () => {
      ;(get as any).mockResolvedValue({ code: 200, data: { id: 5, name: 'C' } })
      const s = useUserStore()
      s.currentUser = { id: 5, name: 'C' } as any
      const r = await s.getUserProfile()
      expect(r).toEqual({ id: 5, name: 'C' })
    })

    it('updateUserProfile = updateUser', async () => {
      ;(put as any).mockResolvedValue({ code: 200, data: { id: 1, name: 'X' } })
      const s = useUserStore()
      await s.updateUserProfile({ name: 'X' }, 1)
      expect(put).toHaveBeenCalledWith('/users/me/profile', { name: 'X' })
    })

    it('uploadAvatar 调用 POST 并返回 response.data', async () => {
      const mockData = { url: '/uploads/1.png' }
      ;(post as any).mockResolvedValue({ code: 200, data: mockData })
      const s = useUserStore()
      const r = await s.uploadAvatar(new File([''], 'a.png'), 1)
      expect(r).toEqual(mockData)
      expect(post).toHaveBeenCalledWith('/users/1/avatar', expect.any(FormData))
    })
  })

  describe('changePassword', () => {
    it('currentUser 已存在时直接 PUT', async () => {
      ;(put as any).mockResolvedValue({ code: 200 })
      const s = useUserStore()
      s.currentUser = { id: 5 } as any
      await s.changePassword('old', 'new')
      expect(put).toHaveBeenCalledWith('/users/5/password', {
        old_password: 'old',
        new_password: 'new',
      })
    })

    it('currentUser 为空时先加载 profile 再改密', async () => {
      ;(get as any).mockResolvedValueOnce({ code: 200, data: { id: 7 } })
      ;(put as any).mockResolvedValue({ code: 200 })
      const s = useUserStore()
      await s.changePassword('o', 'n')
      expect(get).toHaveBeenCalledWith('/users/me')
      expect(put).toHaveBeenCalledWith('/users/7/password', expect.anything())
    })

    it('profile 加载失败后抛出错误', async () => {
      ;(get as any).mockRejectedValue(new Error('401'))
      const s = useUserStore()
      await expect(s.changePassword('o', 'n')).rejects.toThrow('无法获取用户信息，请重新登录')
    })

    it('profile 无有效数据时抛出错误', async () => {
      ;(get as any).mockResolvedValue({ code: 500 })
      const s = useUserStore()
      await expect(s.changePassword('o', 'n')).rejects.toThrow('无法获取用户信息，请重新登录')
    })
  })

  describe('getUserProfile / updateUserProfile', () => {
    it('getUserProfile 带 userId 且接口失败时回退 fetchUser', async () => {
      ;(get as any).mockResolvedValueOnce({ code: 500 })
      ;(get as any).mockResolvedValueOnce({ id: 12, username: 'fallback' })
      const s = useUserStore()
      const r = await s.getUserProfile(12)
      expect(r).toEqual({ id: 12, username: 'fallback' })
      expect(s.currentUser).toEqual({ id: 12, username: 'fallback' })
    })

    it('updateUserProfile 成功但无 data 时返回 res', async () => {
      ;(put as any).mockResolvedValue({ code: 200 })
      const s = useUserStore()
      const r = await s.updateUserProfile({ name: 'x' })
      expect(r).toEqual({ code: 200 })
      expect(s.currentUser).toBeNull()
    })

    it('updateUserProfile 失败时抛出更新失败', async () => {
      ;(put as any).mockResolvedValue({ code: 500 })
      const s = useUserStore()
      await expect(s.updateUserProfile({ name: 'x' })).rejects.toThrow('更新失败')
    })
  })

  describe('uploadAvatar / _getCurrentUserId', () => {
    it('无 userId 时使用 currentUser.id', async () => {
      ;(post as any).mockResolvedValue({ code: 200, data: { url: 'u1' } })
      const s = useUserStore()
      s.currentUser = { id: 3 } as any
      const r = await s.uploadAvatar(new File([''], 'a.png'))
      expect(r).toEqual({ url: 'u1' })
      expect(post).toHaveBeenCalledWith('/users/3/avatar', expect.any(FormData))
    })

    it('currentUser 为空但 token 含 user_id 时解析 JWT', async () => {
      ;(post as any).mockResolvedValue({ data: { url: 'u2' } })
      const payload = Buffer.from(JSON.stringify({ sub: 'alice', user_id: 21 })).toString('base64')
      ;(AuthStorage.getToken as any).mockReturnValue(`header.${payload}.sig`)
      const s = useUserStore()
      const r = await s.uploadAvatar(new File([''], 'a.png'))
      expect(r).toEqual({ url: 'u2' })
      expect(post).toHaveBeenCalledWith('/users/21/avatar', expect.any(FormData))
    })

    it('token 中无 user_id 时抛出', async () => {
      const payload = Buffer.from(JSON.stringify({ sub: 'alice' })).toString('base64')
      ;(AuthStorage.getToken as any).mockReturnValue(`h.${payload}.s`)
      const s = useUserStore()
      await expect(s.uploadAvatar(new File([''], 'a.png'))).rejects.toThrow('无法获取用户ID，请重新登录')
    })

    it('token 无法解析（非法 payload）时抛出', async () => {
      const payload = Buffer.from('not-json').toString('base64')
      ;(AuthStorage.getToken as any).mockReturnValue(`h.${payload}.s`)
      const s = useUserStore()
      await expect(s.uploadAvatar(new File([''], 'a.png'))).rejects.toThrow('无法获取用户ID，请重新登录')
    })

    it('token 格式非法（缺少分段）时抛出', async () => {
      ;(AuthStorage.getToken as any).mockReturnValue('not-a-jwt')
      const s = useUserStore()
      await expect(s.uploadAvatar(new File([''], 'a.png'))).rejects.toThrow('无法获取用户ID，请重新登录')
    })

    it('无任何身份信息时抛出', async () => {
      ;(AuthStorage.getToken as any).mockReturnValue(null)
      const s = useUserStore()
      await expect(s.uploadAvatar(new File([''], 'a.png'))).rejects.toThrow('无法获取用户ID，请重新登录')
    })

    it('响应无 data 时返回原始 res', async () => {
      ;(post as any).mockResolvedValue({ code: 200 })
      const s = useUserStore()
      s.currentUser = { id: 3 } as any
      const r = await s.uploadAvatar(new File([''], 'a.png'))
      expect(r).toEqual({ code: 200 })
    })
  })
})
