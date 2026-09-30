import { describe, it, expect, beforeEach } from 'vitest'
import { isOfflineMode, getMockResponse } from '@/utils/offlineMock'

describe('utils/offlineMock', () => {
  beforeEach(() => {
    sessionStorage.clear()
  })

  describe('isOfflineMode', () => {
    it('无 token 返回 false', () => {
      expect(isOfflineMode()).toBe(false)
    })
    it('普通 token 返回 false', () => {
      sessionStorage.setItem('auth_token', 'some-jwt')
      expect(isOfflineMode()).toBe(false)
    })
    it('builtin token 返回 true', () => {
      sessionStorage.setItem('auth_token', 'builtin-token-admin')
      expect(isOfflineMode()).toBe(true)
    })
  })

  describe('getMockResponse', () => {
    describe('GET 认证', () => {
      it('/auth/me 有用户时返回用户', () => {
        const user = { id: 1, username: 'test' }
        // 凭据同源（fail-closed）：token 与 user 必须同源，缺 token 时视为未登录
        sessionStorage.setItem('auth_token', 'tok-1')
        sessionStorage.setItem('auth_user', JSON.stringify(user))
        expect(getMockResponse('GET', '/api/v1/auth/me').data).toEqual(user)
      })
      it('/auth/me 无用户时返回 null', () => {
        expect(getMockResponse('GET', '/api/v1/auth/me')).toBeNull()
      })
    })

    describe('GET 仪表盘', () => {
      it('/dashboard/stats', () => {
        expect(getMockResponse('GET', '/api/v1/dashboard/stats').data.village_count).toBe(24)
      })
      it('/dashboard', () => {
        expect(getMockResponse('GET', '/api/v1/dashboard').data.village_count).toBe(24)
      })
    })

    describe('GET 帮扶村（旧路由）', () => {
      it('列表', () => {
        const r = getMockResponse('GET', '/api/v1/villages')
        expect(r.data.items.length).toBe(5)
        expect(r.data.total).toBe(5)
      })
      it('详情命中', () => {
        expect(getMockResponse('GET', '/api/v1/villages/2').data.name).toBe('向阳村')
      })
      it('详情未命中回退第一个', () => {
        expect(getMockResponse('GET', '/api/v1/villages/999').data.name).toBe('红星村')
      })
    })

    describe('GET 帮扶村（新路由）', () => {
      it('列表', () => {
        expect(getMockResponse('GET', '/api/v1/supported-villages').data.items.length).toBe(5)
      })
      it('详情命中', () => {
        expect(getMockResponse('GET', '/api/v1/supported-villages/3').data.name).toBe('青山村')
      })
      it('详情未命中回退', () => {
        expect(getMockResponse('GET', '/api/v1/supported-villages/99').data.name).toBe('红星村')
      })
    })

    describe('GET 帮扶学校', () => {
      it('列表', () => {
        expect(getMockResponse('GET', '/api/v1/schools').data.items.length).toBe(4)
      })
      it('详情命中', () => {
        expect(getMockResponse('GET', '/api/v1/schools/2').data.name).toBe('八一中学')
      })
      it('详情未命中回退', () => {
        expect(getMockResponse('GET', '/api/v1/schools/99').data.name).toBe('红星希望小学')
      })
    })

    describe('GET 帮扶项目', () => {
      it('列表', () => {
        expect(getMockResponse('GET', '/api/v1/projects').data.items.length).toBe(5)
      })
      it('详情命中', () => {
        expect(getMockResponse('GET', '/api/v1/projects/2').data.name).toBe('校舍翻新项目')
      })
      it('详情未命中回退', () => {
        expect(getMockResponse('GET', '/api/v1/projects/99').data.name).toBe('村道硬化工程')
      })
    })

    describe('GET 经费', () => {
      it('列表', () => {
        const r = getMockResponse('GET', '/api/v1/funds')
        expect(r.data.items.length).toBe(4)
        expect(r.data.total).toBe(4)
      })
    })

    describe('GET 政策', () => {
      it('列表', () => {
        expect(getMockResponse('GET', '/api/v1/policies').data.items.length).toBe(3)
      })
      it('详情命中', () => {
        expect(getMockResponse('GET', '/api/v1/policies/2').data.title).toContain('巩固拓展')
      })
      it('详情未命中回退', () => {
        expect(getMockResponse('GET', '/api/v1/policies/99').data.title).toBe('乡村振兴促进法')
      })
    })

    describe('GET 用户/组织', () => {
      it('/users 列表', () => {
        expect(getMockResponse('GET', '/api/v1/users').data.items.length).toBe(3)
      })
      it('/organizations 列表', () => {
        expect(getMockResponse('GET', '/api/v1/organizations').data.items.length).toBe(4)
      })
    })

    it('/menus/accessible', () => {
      const r = getMockResponse('GET', '/api/v1/menus/accessible')
      expect(r.data).toEqual({ success: true, data: [], source: 'offline' })
    })

    describe('GET 审批', () => {
      it('/approval/workflows', () => {
        expect(getMockResponse('GET', '/api/v1/approval/workflows').data.length).toBe(2)
      })
      it('/approval/workflows/1', () => {
        expect(getMockResponse('GET', '/api/v1/approval/workflows/1').data.name).toBe(
          '经费审批流程'
        )
      })
      it('/approval/workflows/999 未命中回退第一个流程', () => {
        expect(getMockResponse('GET', '/api/v1/approval/workflows/999').data.name).toBe(
          '经费审批流程'
        )
      })
      it('/approval/tasks/pending', () => {
        const r = getMockResponse('GET', '/api/v1/approval/tasks/pending')
        expect(r.data.every((t: any) => t.status === 'pending')).toBe(true)
      })
      it('/approval/tasks/all', () => {
        expect(getMockResponse('GET', '/api/v1/approval/tasks/all').data.length).toBe(3)
      })
      it('/approval/history', () => {
        expect(getMockResponse('GET', '/api/v1/approval/history').data.length).toBe(3)
      })
      it('/approval/tasks/1/diff', () => {
        const r = getMockResponse('GET', '/api/v1/approval/tasks/1/diff')
        expect(r.data.diff_fields).toEqual(['amount', 'status'])
      })
      it('其他审批路径返回空数组', () => {
        expect(getMockResponse('GET', '/api/v1/approval/other').data).toEqual([])
      })
    })

    describe('GET 工作日志', () => {
      it('列表', () => {
        expect(getMockResponse('GET', '/api/v1/work-logs').data.items.length).toBe(3)
      })
      it('详情命中', () => {
        expect(getMockResponse('GET', '/api/v1/work-logs/2').data.title).toBe('向阳村学校捐赠仪式')
      })
      it('详情未命中回退', () => {
        expect(getMockResponse('GET', '/api/v1/work-logs/99').data.title).toBe('红星村入户走访调研')
      })
      it('/work-logs/calendar', () => {
        const r = getMockResponse('GET', '/api/v1/work-logs/calendar')
        expect(r.data.items.length).toBe(3)
        expect(r.data.year).toBe(2026)
      })
      it('其他路径返回空列表', () => {
        expect(getMockResponse('GET', '/api/v1/work-logs/other').data.items).toEqual([])
      })
    })

    describe('GET 乡村工作', () => {
      it('列表', () => {
        const r = getMockResponse('GET', '/api/v1/rural-works')
        expect(r.data.items.length).toBe(3)
      })
      it('详情命中', () => {
        expect(getMockResponse('GET', '/api/v1/rural-works/1').data.data.name).toBe(
          '红星村道路硬化工程'
        )
      })
      it('详情未命中回退', () => {
        expect(getMockResponse('GET', '/api/v1/rural-works/99').data.data.name).toBe(
          '红星村道路硬化工程'
        )
      })
      it('/rural-works/statistics/summary', () => {
        expect(
          getMockResponse('GET', '/api/v1/rural-works/statistics/summary').data.data.total
        ).toBe(3)
      })
      it('/rural-works/villages', () => {
        expect(getMockResponse('GET', '/api/v1/rural-works/villages').data.data.length).toBe(3)
      })
      it('/rural-works/years', () => {
        expect(getMockResponse('GET', '/api/v1/rural-works/years').data.data).toEqual([
          2024, 2025, 2026,
        ])
      })
      it('/rural-works/report/generate', () => {
        const r = getMockResponse('GET', '/api/v1/rural-works/report/generate')
        expect(r.data.data.total).toBe(3)
        expect(r.data.data.generated_at).toBeDefined()
      })
      it('其他路径返回空列表', () => {
        const r = getMockResponse('GET', '/api/v1/rural-works/other')
        expect(r.data.items).toEqual([])
        expect(r.data.total).toBe(0)
      })
    })

    describe('GET 消息', () => {
      it('列表', () => {
        const r = getMockResponse('GET', '/api/v1/messages')
        expect(r.data.items.length).toBe(3)
        expect(r.data.unread_count).toBe(2)
      })
      it('/messages/unread-count', () => {
        expect(getMockResponse('GET', '/api/v1/messages/unread-count').data.count).toBe(2)
      })
      it('其他路径返回空数组', () => {
        expect(getMockResponse('GET', '/api/v1/messages/1')).toEqual({ data: [] })
      })
    })

    describe('GET 通知偏好', () => {
      it('/notifications/preferences', () => {
        const r = getMockResponse('GET', '/api/v1/notifications/preferences')
        expect(r.data.email_approval).toBe(true)
      })
      it('其他路径返回空对象', () => {
        expect(getMockResponse('GET', '/api/v1/notifications/other')).toEqual({ data: {} })
      })
    })

    describe('GET 数据同步', () => {
      it('/data-sync/logs', () => {
        const r = getMockResponse('GET', '/api/v1/data-sync/logs')
        expect(r.data.count).toBe(2)
      })
      it('/data-sync/conflicts/1', () => {
        const r = getMockResponse('GET', '/api/v1/data-sync/conflicts/1')
        expect(r.data.data).toEqual([])
      })
      it('其他路径返回成功', () => {
        const r = getMockResponse('GET', '/api/v1/data-sync/something')
        expect(r['data']['success']).toBe(true)
      })
    })

    describe('GET 机器码', () => {
      it('/machine-code/get-machine-code', () => {
        const r = getMockResponse('GET', '/api/v1/machine-code/get-machine-code')
        expect(r.data.data.machine_code).toBeDefined()
      })
      it('/machine-code/admin/list', () => {
        const r = getMockResponse('GET', '/api/v1/machine-code/admin/list')
        expect(r.data.data.items.length).toBe(2)
      })
      it('/machine-code/machine-info', () => {
        const r = getMockResponse('GET', '/api/v1/machine-code/machine-info')
        expect(r.data.system).toBe('Windows')
      })
      it('其他路径返回成功', () => {
        expect(getMockResponse('GET', '/api/v1/machine-code/other')['data']['success']).toBe(true)
      })
    })

    describe('GET 统计', () => {
      it('/stats 后缀', () => {
        expect(getMockResponse('GET', '/api/v1/anything/stats').data.village_count).toBe(24)
      })
      it('/statistics 后缀', () => {
        expect(getMockResponse('GET', '/api/v1/anything/statistics').data.village_count).toBe(24)
      })
    })

    describe('GET 兜底', () => {
      it('未知路径返回空列表', () => {
        const r = getMockResponse('GET', '/api/v1/unknown-endpoint')
        expect(r.data.items).toEqual([])
        expect(r.data.total).toBe(0)
      })
    })

    describe('URL 规范化', () => {
      it('完整 URL', () => {
        expect(
          getMockResponse('GET', 'http://localhost:3000/api/v1/villages').data.items.length
        ).toBe(5)
      })
      it('https URL 无 /api/v1 前缀', () => {
        expect(getMockResponse('GET', 'https://example.com/villages').data.items.length).toBe(5)
      })
      it('查询字符串', () => {
        expect(getMockResponse('GET', '/api/v1/projects?page=2&size=10').data.items.length).toBe(5)
      })
      it('尾部斜杠', () => {
        expect(getMockResponse('GET', '/api/v1/projects/').data.items.length).toBe(5)
      })
      it('无前导斜杠', () => {
        expect(getMockResponse('get', 'villages').data.items.length).toBe(5)
      })
      it('仅 /api/v1/', () => {
        const r = getMockResponse('GET', '/api/v1/')
        expect(r.data.items).toEqual([])
      })
    })

    describe('POST 请求', () => {
      it('/import/projects/parse 返回预览', () => {
        const r = getMockResponse('POST', '/api/v1/import/projects/parse')
        expect(r.data.preview.length).toBe(2)
      })
      it('/import/projects 返回导入结果', () => {
        const r = getMockResponse('POST', '/api/v1/import/projects')
        expect(r.data.data.total_rows).toBe(5)
        expect(r.data.message).toContain('离线')
      })
      it('/import/villages 返回导入结果', () => {
        const r = getMockResponse('POST', '/api/v1/import/villages')
        expect(r.data.data.success_rows).toBe(5)
      })
      it('其他 POST 返回离线 id', () => {
        const r = getMockResponse('POST', '/api/v1/projects')
        expect(r.data.data.id).toMatch(/^offline-/)
        expect(r.data.message).toContain('离线')
      })
    })

    describe('PUT/PATCH/DELETE', () => {
      it('PUT 返回更新成功', () => {
        const r = getMockResponse('PUT', '/api/v1/projects/1')
        expect(r['data']['success']).toBe(true)
        expect(r.data.message).toContain('更新')
      })
      it('PATCH 返回更新成功', () => {
        const r = getMockResponse('PATCH', '/api/v1/projects/1')
        expect(r.data.message).toContain('更新')
      })
      it('DELETE 返回删除成功', () => {
        const r = getMockResponse('DELETE', '/api/v1/projects/1')
        expect(r.data.message).toContain('删除')
      })
    })

    it('未知方法返回空列表', () => {
      const r = getMockResponse('OPTIONS', '/api/v1/test')
      expect(r.data.items).toEqual([])
    })
  })
})
