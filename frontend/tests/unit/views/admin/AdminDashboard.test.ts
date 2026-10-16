/**
 * AdminDashboard.vue 组件测试
 *
 * 覆盖目标：src/views/admin/AdminDashboard.vue 100%（stmts/branches/functions/lines）
 *
 * M42 契约变更（本次重写的原因）：
 *   原实现只调 /dashboard/stats，却去读 system_status / recent_logins / audit_logs /
 *   pending_items / storage 五个该端点**从不返回**的键 → 5 个区域恒为空；
 *   adminStats[1]「今日活跃」实际展示 total_population。
 *   现改为各面板接各自真实端点：
 *     概览   ← GET /dashboard/stats
 *     今日活跃 ← GET /system/audit/stats（active_users）
 *     系统状态 ← GET /system/monitor/snapshot
 *     存储   ← GET /system/monitor/database-size + /system/backup/stats + /system-health/disk-space
 *     最近登录 ← GET /system/audit/login-attempts
 *     审计日志 ← GET /system/audit/logs
 *     待处理   ← GET /approval/tasks/pending
 *   故旧用例中"读 /dashboard/stats 的假字段"断言属**锁定旧错误契约**，随实现一并订正。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'

// ==================== Mocks ====================

const mockPush = vi.fn(() => Promise.resolve())
const mockResolve = vi.fn(() => ({ name: 'SomeRoute', matched: [{ path: '/x' }] }))
vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush, resolve: mockResolve }),
  useRoute: () => ({ params: {}, query: {} }),
}))

const mockGet = vi.fn()
vi.mock('@/api/request', () => ({
  get: (...args: any[]) => mockGet(...args),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  getCsrfToken: vi.fn(() => Promise.resolve('test-csrf')),
}))

const mockLoggerError = vi.fn()
vi.mock('@/utils/logger', () => ({
  logger: {
    error: (...args: any[]) => mockLoggerError(...args),
    warn: vi.fn(),
    info: vi.fn(),
    debug: vi.fn(),
    log: vi.fn(),
  },
}))

import AdminDashboard from '@/views/admin/AdminDashboard.vue'
import { useUserStore } from '@/stores/user'
import { AuthStorage } from '@/utils/authStorage'

// ==================== Helpers ====================

/** 各端点默认响应（envelope 展开后的形态：payload 字段已在顶层，data 保留） */
const payloads: Record<string, any> = {
  '/dashboard/stats': {
    data: { total_users: 42, total_villages: 100, total_projects: 400, total_schools: 24 },
  },
  '/system/audit/stats': { data: { active_users: 5 } },
  '/system/monitor/snapshot': {
    data: { cpu_usage: 12.5, memory_usage: 30, disk_usage: 55.5, status: 'healthy' },
  },
  '/system/monitor/database-size': { data: { size_bytes: 1048576 } },
  '/system/backup/stats': { data: { totalSize: 2097152 } },
  '/system-health/disk-space': { data: { total_gb: 100, used_percent: 50 } },
  '/system/audit/login-attempts': {
    items: [
      { id: 1, username: '张三', success: true, attemptTime: '2026-01-01T10:00:00', ipAddress: '10.0.0.1' },
      { id: 2, username: '李四', success: false, attemptTime: 'not-a-date', ip_address: '10.0.0.2' },
      { id: 3, username: '', success: true, attempt_time: 'not-a-date' },
    ],
  },
  '/system/audit/logs': {
    items: [
      { id: 1, level: 'error', action: '删除数据', username: 'admin', resource_type: '项目', created_at: '2026-01-01T10:00:00' },
      { id: 2, level: 'info', action: '登录系统', created_at: 'bad-date' },
    ],
  },
  '/approval/tasks/pending': {
    items: [
      { id: 1, priority: 5, entity_type: '项目', title: '审批A', created_at: '2026-01-01T10:00:00' },
      { id: 2, priority: 0, title: '审批B' },
    ],
  },
}

/** 按 URL 路由 mockGet；rejects 中的 URL 一律 reject */
function routeGet(overrides: Record<string, any> = {}, rejects: string[] = []) {
  mockGet.mockImplementation((url: string) => {
    if (rejects.includes(url)) return Promise.reject(new Error(url + ' boom'))
    if (url in overrides) return Promise.resolve(overrides[url])
    return Promise.resolve(payloads[url] ?? {})
  })
}

function setupPinia(role: string | null = 'admin') {
  const pinia = createPinia()
  setActivePinia(pinia)
  const userStore = useUserStore(pinia)
  userStore.currentUser = role ? ({ id: 1, username: 'u', role } as any) : null
  // isAdminUser() 默认读 AuthStorage；写入一份同源凭据让两种口径一致
  sessionStorage.clear()
  if (role) {
    sessionStorage.setItem('auth_token', 't')
    sessionStorage.setItem('auth_user', JSON.stringify({ id: 1, username: 'u', role }))
  }
  return pinia
}

function mountDashboard(role: string | null = 'admin') {
  const pinia = setupPinia(role)
  return mount(AdminDashboard, {
    global: {
      plugins: [pinia],
      stubs: {
        'el-icon': { template: '<i><slot/></i>' },
      },
    },
  })
}

// ==================== 测试 ====================

beforeEach(() => {
  vi.clearAllMocks()
  routeGet()
})

describe('权限分支', () => {
  it('admin 角色渲染管理控制台', async () => {
    const wrapper = mountDashboard('admin')
    await flushPromises()
    expect(wrapper.find('.admin-dashboard').exists()).toBe(true)
    expect(wrapper.text()).toContain('管理控制台')
  })

  it('super_admin 角色同样有权限', async () => {
    const wrapper = mountDashboard('super_admin')
    await flushPromises()
    expect(wrapper.find('.admin-dashboard').exists()).toBe(true)
  })

  it('普通角色渲染无权限提示', async () => {
    const wrapper = mountDashboard('viewer')
    await flushPromises()
    expect(wrapper.find('.admin-dashboard').exists()).toBe(false)
  })

  it('未登录用户渲染无权限提示', async () => {
    const wrapper = mountDashboard(null)
    await flushPromises()
    expect(wrapper.find('.admin-dashboard').exists()).toBe(false)
  })
})

describe('数据加载：各面板接真实端点（M42）', () => {
  it('每个面板调用各自的真实端点，不再读 /dashboard/stats 的假字段', async () => {
    mountDashboard()
    await flushPromises()

    const urls = mockGet.mock.calls.map((c: any[]) => c[0])
    expect(urls).toContain('/dashboard/stats')
    expect(urls).toContain('/system/audit/stats')
    expect(urls).toContain('/system/monitor/snapshot')
    expect(urls).toContain('/system/monitor/database-size')
    expect(urls).toContain('/system/backup/stats')
    expect(urls).toContain('/system-health/disk-space')
    expect(urls).toContain('/system/audit/login-attempts')
    expect(urls).toContain('/system/audit/logs')
    expect(urls).toContain('/approval/tasks/pending')
  })

  it('加载成功：概览统计 / 今日活跃 / 系统状态 / 存储 / 三列表全部填充', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.adminStats[0].value).toBe(42)
    // 今日活跃 ← /system/audit/stats 的 active_users（不再是 total_population）
    expect(vm.adminStats[1].value).toBe(5)
    // 数据记录 = 帮扶村100 + 项目400 + 学校24（total_funds 单位万元，不得混入条数）
    expect(vm.adminStats[2].value).toBe(524)
    expect(vm.adminStats[3].value).toBe('100 村 / 400 项目')

    // 系统状态：CPU/内存/磁盘 + 采集状态
    expect(vm.systemStatus).toHaveLength(4)
    expect(vm.systemStatus[0]).toEqual({ name: 'CPU 使用率', status: 'online', statusText: '12.5%' })
    expect(vm.systemStatus[3]).toEqual({ name: '采集状态', status: 'online', statusText: '正常' })

    // 最近登录：只保留成功记录，非法时间回落 '--'，缺用户名回落 '未知用户'
    expect(vm.recentLogins).toHaveLength(2)
    expect(vm.recentLogins[0]).toEqual({ id: 1, name: '张三', avatar: '张', time: '2026-01-01 10:00', ip: '10.0.0.1' })
    expect(vm.recentLogins[1].name).toBe('未知用户')
    // 头像取原始用户名首字母：空用户名回落 'U'（而非占位名首字「未」）
    expect(vm.recentLogins[1].avatar).toBe('U')
    expect(vm.recentLogins[1].time).toBe('--')

    // 审计日志：level 映射标签类型，缺字段回落
    expect(vm.auditLogs).toHaveLength(2)
    expect(vm.auditLogs[0].type).toBe('danger')
    expect(vm.auditLogs[0].target).toBe('项目')
    expect(vm.auditLogs[1].type).toBe('info')
    expect(vm.auditLogs[1].user).toBe('系统')
    expect(vm.auditLogs[1].time).toBe('--')

    // 待处理：priority 整数 → high/low
    expect(vm.pendingItems).toHaveLength(2)
    expect(vm.pendingItems[0]).toMatchObject({ priority: 'high', type: '项目', description: '审批A' })
    expect(vm.pendingItems[1]).toMatchObject({ priority: 'low', type: '审批', description: '审批B' })

    // 存储：库文件 1MB + 备份 2MB；容量取磁盘 100GB、进度按已用率 50%
    expect(vm.dbSize).toBe(1048576)
    expect(vm.backupSize).toBe(2097152)
    expect(vm.logSize).toBe(0)
    expect(vm.storageTotal).toBe(100 * 1024 ** 3)
    expect(vm.storageUsed).toBe((100 * 1024 ** 3 * 50) / 100)
    expect(vm.storageError).toBe(false)

    // 渲染断言
    expect(wrapper.text()).toContain('CPU 使用率')
    expect(wrapper.text()).toContain('张三')
    expect(wrapper.text()).toContain('删除数据')
    expect(wrapper.text()).toContain('审批A')
    expect(wrapper.find('.pending-count').text()).toBe('2')
    expect(wrapper.text()).not.toContain('加载中...')
  })

  it('边界回落：critical 级别 / 空 action / 缺 title / total_projects 缺失', async () => {
    routeGet({
      // total_villages 有值而 total_projects 缺失 → 概览文案回落 `?? 0`
      '/dashboard/stats': { data: { total_users: 1, total_villages: 7 } },
      '/system/audit/logs': {
        items: [
          // critical 命中第二操作数（danger）；action 为空串回落 '--'
          { id: 1, level: 'critical', action: '', created_at: '2026-01-01T00:00:00' },
          // 全字段缺失：level/action 都走兜底（info / '--'）
          { id: 2 },
        ],
      },
      '/approval/tasks/pending': { items: [{ id: 1, priority: 0 }] },
    })
    const wrapper = mountDashboard()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.adminStats[3].value).toBe('7 村 / 0 项目')

    expect(vm.auditLogs[0].type).toBe('danger')
    expect(vm.auditLogs[0].action).toBe('--')
    expect(vm.auditLogs[1].type).toBe('info')
    expect(vm.auditLogs[1].action).toBe('--')

    expect(vm.pendingItems[0].description).toBe('--')
  })

  it('存储面板：错误文案为空时模板回落默认提示', async () => {
    routeGet({}, ['/system/monitor/database-size'])
    const wrapper = mountDashboard()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.storageError).toBe(true)
    // 后端 detail 为空 / 异常无 message 时 errText 可能得空串 → 模板 `|| '存储信息加载失败'` 兜底
    vm.panelError.storage = ''
    await nextTick()
    expect(wrapper.find('.error-tip').text()).toContain('存储信息加载失败')
  })

  it('加载中：请求未返回前展示「加载中...」而非空态', async () => {
    const wrapper = mountDashboard()
    // 不 await：panelsLoaded 仍为 false
    expect(wrapper.text()).toContain('加载中...')
    await flushPromises()
    expect(wrapper.text()).not.toContain('加载中...')
  })

  it('空数据：全部端点返回空 → 各面板展示空态文案', async () => {
    routeGet({
      '/dashboard/stats': { data: {} },
      '/system/audit/stats': { data: {} },
      '/system/monitor/snapshot': { data: {} },
      '/system/monitor/database-size': { data: {} },
      '/system/backup/stats': { data: {} },
      '/system-health/disk-space': { data: {} },
      '/system/audit/login-attempts': { items: [] },
      '/system/audit/logs': { items: [] },
      '/approval/tasks/pending': { items: [] },
    })
    const wrapper = mountDashboard()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.adminStats[0].value).toBe(0)
    expect(vm.adminStats[1].value).toBe('--')
    expect(vm.adminStats[2].value).toBe(0)
    expect(vm.adminStats[3].value).toBe('--')
    expect(vm.systemStatus).toHaveLength(0)
    expect(wrapper.text()).toContain('暂无状态数据')
    expect(wrapper.text()).toContain('暂无登录记录')
    expect(wrapper.text()).toContain('暂无审计记录')
    expect(wrapper.text()).toContain('暂无待处理事项')
  })

  it('envelope 未展开（嵌套 data）也能解析统计', async () => {
    routeGet({ '/dashboard/stats': { data: { total_users: 88 } } })
    const wrapper = mountDashboard()
    await flushPromises()
    expect((wrapper.vm as any).adminStats[0].value).toBe(88)
  })

  it('裸 payload（无信封包装）也能解析', async () => {
    routeGet({ '/dashboard/stats': { total_users: 66, total_villages: 3, total_projects: 4 } })
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.adminStats[0].value).toBe(66)
    expect(vm.adminStats[3].value).toBe('3 村 / 4 项目')
  })

  it('裸数组响应（pickItems 第一分支）', async () => {
    routeGet({ '/system/audit/logs': [{ id: 9, level: 'warning', action: '导出', created_at: '2026-01-01T00:00:00' }] })
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.auditLogs).toHaveLength(1)
    expect(vm.auditLogs[0].type).toBe('warning')
  })

  it('res.data 为 null → 概览归零；res 为 null → 同样归零', async () => {
    routeGet({ '/dashboard/stats': { data: null } })
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.adminStats[0].value).toBe(0)
    expect(vm.adminStats[2].value).toBe(0)

    mockGet.mockClear()
    routeGet({ '/dashboard/stats': null })
    const wrapper2 = mountDashboard()
    await flushPromises()
    const vm2 = wrapper2.vm as any
    expect(vm2.adminStats[0].value).toBe(0)
    expect(vm2.adminStats[3].value).toBe('--')
  })

  it('概览接口失败：记录日志且统计保持默认', async () => {
    routeGet({}, ['/dashboard/stats'])
    const wrapper = mountDashboard()
    await flushPromises()
    expect(mockLoggerError).toHaveBeenCalled()
    expect((wrapper.vm as any).adminStats[0].value).toBe(0)
  })

  it('今日活跃：active_users 非数字 → 展示 "--"（不伪装成 0）', async () => {
    routeGet({ '/system/audit/stats': { data: { active_users: 'many' } } })
    const wrapper = mountDashboard()
    await flushPromises()
    expect((wrapper.vm as any).adminStats[1].value).toBe('--')
  })

  it('今日活跃接口失败 → "--" 且记录日志', async () => {
    routeGet({}, ['/system/audit/stats'])
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.adminStats[1].value).toBe('--')
    expect(mockLoggerError).toHaveBeenCalledWith('加载活跃用户数失败:', expect.any(Error))
  })

  it('系统状态：高占用标 offline；status=limited/error 各自文案', async () => {
    routeGet({
      '/system/monitor/snapshot': {
        data: { cpu_usage: 95, memory_usage: 'n/a', disk_usage: 99, status: 'limited' },
      },
    })
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.systemStatus).toEqual([
      { name: 'CPU 使用率', status: 'offline', statusText: '95.0%' },
      { name: '磁盘使用率', status: 'offline', statusText: '99.0%' },
      { name: '采集状态', status: 'offline', statusText: '受限' },
    ])

    mockGet.mockClear()
    routeGet({ '/system/monitor/snapshot': { data: { cpu_usage: 1, status: 'error' } } })
    const w2 = mountDashboard()
    await flushPromises()
    expect((w2.vm as any).systemStatus[1]).toEqual({
      name: '采集状态',
      status: 'offline',
      statusText: '异常',
    })
  })

  it('系统状态：无 status 字段 → 不追加采集状态行', async () => {
    routeGet({ '/system/monitor/snapshot': { data: { cpu_usage: 1 } } })
    const wrapper = mountDashboard()
    await flushPromises()
    expect((wrapper.vm as any).systemStatus).toHaveLength(1)
  })

  it('系统状态接口失败 → 空列表 + 面板错误文案', async () => {
    routeGet({}, ['/system/monitor/snapshot'])
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.systemStatus).toHaveLength(0)
    expect(wrapper.text()).toContain('/system/monitor/snapshot boom')
    expect(wrapper.find('.error-tip').exists()).toBe(true)
  })

  it('存储：磁盘端点失败 → 退化为「已用 = 库+备份」且 total ≥ used', async () => {
    routeGet({}, ['/system-health/disk-space'])
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.storageUsed).toBe(1048576 + 2097152)
    expect(vm.storageTotal).toBe(1048576 + 2097152)
    expect(vm.storageError).toBe(false)
  })

  it('存储：磁盘端点返回但缺 used_percent → 已用取库+备份、总量取磁盘', async () => {
    routeGet({ '/system-health/disk-space': { data: { total_gb: 10 } } })
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.storageTotal).toBe(10 * 1024 ** 3)
    expect(vm.storageUsed).toBe(1048576 + 2097152)
  })

  it('存储：total_gb 非法 → 回落「已用=库+备份」并保证非零分母', async () => {
    routeGet({
      '/system-health/disk-space': { data: { total_gb: 'x', used_percent: 10 } },
      '/system/monitor/database-size': { data: { size_bytes: 0 } },
      '/system/backup/stats': { data: { totalSize: 0 } },
    })
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.storageUsed).toBe(0)
    expect(vm.storageTotal).toBe(1)
    expect(vm.storagePercent).toBe(0)
  })

  it('存储：库/备份端点失败 → storageError 与错误文案', async () => {
    routeGet({}, ['/system/monitor/database-size'])
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.storageError).toBe(true)
    expect(wrapper.text()).toContain('/system/monitor/database-size boom')
  })

  it('最近登录接口失败 → 空列表 + 错误文案', async () => {
    routeGet({}, ['/system/audit/login-attempts'])
    const wrapper = mountDashboard()
    await flushPromises()
    expect((wrapper.vm as any).recentLogins).toHaveLength(0)
    expect(wrapper.text()).toContain('/system/audit/login-attempts boom')
  })

  it('审计日志接口失败 → 空列表 + 错误文案', async () => {
    routeGet({}, ['/system/audit/logs'])
    const wrapper = mountDashboard()
    await flushPromises()
    expect((wrapper.vm as any).auditLogs).toHaveLength(0)
    expect(wrapper.text()).toContain('/system/audit/logs boom')
  })

  it('待处理接口失败 → 空列表 + 错误文案', async () => {
    routeGet({}, ['/approval/tasks/pending'])
    const wrapper = mountDashboard()
    await flushPromises()
    expect((wrapper.vm as any).pendingItems).toHaveLength(0)
    expect(wrapper.text()).toContain('/approval/tasks/pending boom')
  })

  it('登录记录 name 为空时头像回退为 U', async () => {
    routeGet({
      '/system/audit/login-attempts': {
        items: [{ id: 9, username: '', success: true, attemptTime: 't', ipAddress: '1.1.1.1' }],
      },
    })
    const wrapper = mountDashboard()
    await flushPromises()
    expect(wrapper.find('.login-avatar').text()).toBe('U')
  })

  it('loadAdminData 二次调用会先复位 panelsLoaded 与面板错误', async () => {
    routeGet({}, ['/system/audit/logs'])
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.panelError.audit).toBeTruthy()

    routeGet()
    const p = vm.loadAdminData()
    expect(vm.panelsLoaded).toBe(false)
    expect(vm.panelError).toEqual({})
    await p
    expect(vm.panelsLoaded).toBe(true)
    expect(vm.panelError).toEqual({})
  })
})

describe('交互', () => {
  it('横幅四个操作按钮均触发 pushSafe', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    const buttons = wrapper.findAll('.admin-actions .action-btn')
    expect(buttons).toHaveLength(4)
    for (const btn of buttons) {
      await btn.trigger('click')
    }

    expect(mockPush).toHaveBeenCalledWith('/system/users')
    expect(mockPush).toHaveBeenCalledWith('/system/backup')
    expect(mockPush).toHaveBeenCalledWith('/system/audit')
    expect(mockPush).toHaveBeenCalledWith('/system/config')
  })

  it('审计日志"查看全部"按钮跳转', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    await wrapper.find('.text-btn').trigger('click')
    expect(mockPush).toHaveBeenCalledWith('/system/audit')
  })

  it('快捷操作点击跳转对应路径', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    const actions = wrapper.findAll('.quick-action')
    expect(actions).toHaveLength(6)
    for (const action of actions) {
      await action.trigger('click')
    }
    expect(mockPush).toHaveBeenCalledWith('/system/roles')
    expect(mockPush).toHaveBeenCalledWith('/data-management')
  })
})

describe('工具函数', () => {
  it('formatSize 覆盖 B/KB/MB/GB 各分支', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.formatSize(512)).toBe('512 B')
    expect(vm.formatSize(2048)).toBe('2.0 KB')
    expect(vm.formatSize(5 * 1024 * 1024)).toBe('5.0 MB')
    expect(vm.formatSize(3 * 1024 * 1024 * 1024)).toBe('3.0 GB')
  })

  it('storagePercent 按 used/total 计算并渲染到宽度', async () => {
    const wrapper = mountDashboard()
    await flushPromises()

    const vm = wrapper.vm as any
    expect(vm.storagePercent).toBe(50)

    vm.storageUsed = 1
    vm.storageTotal = 4
    await nextTick()
    expect(vm.storagePercent).toBe(25)
  })

  it('fmtTime 非法/空值回落 --，合法值格式化', async () => {
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.fmtTime(undefined)).toBe('--')
    expect(vm.fmtTime('')).toBe('--')
    expect(vm.fmtTime('bad')).toBe('--')
    expect(vm.fmtTime('2026-03-04T05:06:07')).toBe('2026-03-04 05:06')
  })

  it('pickItems / pickData 兼容裸数组、items、data 嵌套与 null', async () => {
    const wrapper = mountDashboard()
    await flushPromises()
    const vm = wrapper.vm as any
    expect(vm.pickItems([1, 2])).toEqual([1, 2])
    expect(vm.pickItems({ items: [3] })).toEqual([3])
    expect(vm.pickItems({ data: { items: [4] } })).toEqual([4])
    expect(vm.pickItems({})).toEqual([])
    expect(vm.pickData({ a: 1 })).toEqual({ a: 1 })
    expect(vm.pickData({ data: { b: 2 } })).toEqual({ b: 2 })
    expect(vm.pickData(null)).toEqual({})
  })
})

describe('isAdminUser 口径（M47）', () => {
  it('存量旧角色 manager 归一化后仍视为管理员', async () => {
    const wrapper = mountDashboard('manager')
    await flushPromises()
    expect(wrapper.find('.admin-dashboard').exists()).toBe(true)
  })

  it('AuthStorage 无凭据但 store 有管理员档案 → 仍按管理员渲染', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const userStore = useUserStore(pinia)
    userStore.currentUser = { id: 1, username: 'u', role: 'super_admin' } as any
    sessionStorage.clear()
    const wrapper = mount(AdminDashboard, { global: { plugins: [pinia] } })
    await flushPromises()
    expect(wrapper.find('.admin-dashboard').exists()).toBe(true)
    // AuthStorage 侧口径仍为 false（无凭据 → fail-closed）
    expect(AuthStorage.getUser()).toBeNull()
  })
})
