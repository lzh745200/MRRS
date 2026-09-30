import { describe, it, expect, beforeEach } from 'vitest'
import { isOfflineMode, getMockResponse } from '@/utils/offlineMock'

describe('offlineMock', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  describe('isOfflineMode', () => {
    it('无 token 时返回 false', () => {
      expect(isOfflineMode()).toBe(false)
    })

    it('普通 token 返回 false', () => {
      sessionStorage.setItem('auth_token', 'some-jwt-token')
      expect(isOfflineMode()).toBe(false)
    })

    it('builtin token 返回 true', () => {
      sessionStorage.setItem('auth_token', 'builtin-token-admin')
      expect(isOfflineMode()).toBe(true)
    })
  })

  describe('getMockResponse', () => {
    describe('GET 请求', () => {
      it('/auth/me 有用户数据时返回用户', () => {
        const user = { id: 1, username: 'test' }
        // 凭据同源（fail-closed）：只有 auth_user 而无 auth_token 时不提供身份，
        // 因此这里必须同时写入 token。
        sessionStorage.setItem('auth_token', 'tok-1')
        sessionStorage.setItem('auth_user', JSON.stringify(user))
        const result = getMockResponse('GET', '/api/v1/auth/me')
        expect(result.data).toEqual(user)
      })

      it('/auth/me 无用户数据时返回 null', () => {
        const result = getMockResponse('GET', '/api/v1/auth/me')
        expect(result).toBeNull()
      })

      it('统计接口返回 mock 统计对象', () => {
        const result = getMockResponse('GET', '/api/v1/projects/stats')
        expect(result.data).toBeDefined()
      })

      it('/statistics 路径返回 mock 统计对象', () => {
        const result = getMockResponse('GET', '/api/v1/funds/statistics')
        expect(result.data).toBeDefined()
      })

      it('/dashboard/stats 返回 mock 仪表盘数据', () => {
        const result = getMockResponse('GET', '/api/v1/dashboard/stats')
        expect(result.data.village_count).toBeDefined()
      })

      it('列表接口返回 mock 数据列表', () => {
        const result = getMockResponse('GET', '/api/v1/projects')
        expect(result.data.items.length).toBeGreaterThan(0)
        expect(result.data.total).toBeGreaterThan(0)
      })

      it('处理无前缀 URL', () => {
        const result = getMockResponse('get', '/projects')
        expect(result.data.items.length).toBeGreaterThan(0)
      })
    })

    describe('POST 请求', () => {
      it('返回成功响应', () => {
        const result = getMockResponse('POST', '/api/v1/projects')
        expect(result['data']['success']).toBe(true)
        expect(result.data.data.id).toMatch(/^offline-/)
      })
    })

    describe('PUT/PATCH 请求', () => {
      it('PUT 返回更新成功', () => {
        const result = getMockResponse('PUT', '/api/v1/projects/1')
        expect(result['data']['success']).toBe(true)
        expect(result.data.message).toContain('更新成功')
      })

      it('PATCH 返回更新成功', () => {
        const result = getMockResponse('PATCH', '/api/v1/projects/1')
        expect(result['data']['success']).toBe(true)
      })
    })

    describe('DELETE 请求', () => {
      it('返回删除成功', () => {
        const result = getMockResponse('DELETE', '/api/v1/projects/1')
        expect(result['data']['success']).toBe(true)
        expect(result.data.message).toContain('删除成功')
      })
    })

    describe('其他方法', () => {
      it('未知方法返回空列表', () => {
        const result = getMockResponse('OPTIONS', '/api/v1/test')
        expect(result.data.items).toEqual([])
      })
    })

    describe('URL 规范化', () => {
      it('处理完整 URL', () => {
        const result = getMockResponse('GET', 'http://localhost:3000/api/v1/projects')
        expect(result.data.items.length).toBeGreaterThan(0)
      })

      it('处理尾部斜杠', () => {
        const result = getMockResponse('GET', '/api/v1/projects/')
        expect(result.data.items.length).toBeGreaterThan(0)
      })
    })
  })
})
